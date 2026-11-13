from dataclasses import dataclass
import re
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml.common import DefusedXmlException
from django.db import transaction
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.utils import json
from rest_framework.views import APIView

from .serializers import (
    DepartmentSelectionSerializer,
    MeasurementSerializer,
    NetworkElementSerializer,
    PhysicalDeviceSerializer,
)
from .views import DepartmentScope
from .writes import lock_metadata_write


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_EXPANDED_BYTES = 25 * 1024 * 1024
MAX_ROWS_PER_SHEET = 2000
REF_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
JSON_COLUMNS = {"location", "geometry", "external_identifiers", "data_collection_config"}
REFERENCE_SHEETS = {"physical_device": "Physical Devices", "network_element": "Network Elements"}


@dataclass(frozen=True)
class Sheet:
    serializer: type
    required: tuple
    optional: tuple


SHEETS = {
    "Physical Devices": Sheet(
        PhysicalDeviceSerializer,
        ("name", "device_type"),
        ("ref", "description", "location"),
    ),
    "Network Elements": Sheet(
        NetworkElementSerializer,
        ("name", "element_type"),
        ("ref", "description", "geometry", "external_identifiers", "dma_model_id", "strategic_model_id"),
    ),
    "Measurements": Sheet(
        MeasurementSerializer,
        ("name", "physical_device", "network_element", "measurement_type", "measurement_unit"),
        ("description", "data_collection_config", "customer_account", "meter_account"),
    ),
}


class RejectedWorkbook(Exception):
    def __init__(self, errors):
        self.errors = errors


def row_error(sheet, row, errors):
    return {"sheet": sheet, "row": row, "errors": errors}


def file_error(message):
    return RejectedWorkbook([row_error(None, None, {"file": [message]})])


def read_sheet(worksheet, spec, errors):
    # The reported Excel dimensions may be wrong. Read the actual cells and
    # stop at the row limit even if the worksheet declares a very large range.
    worksheet.reset_dimensions()
    rows = worksheet.iter_rows()
    headers = [cell.value for cell in next(rows, ())]
    while headers and headers[-1] is None:
        headers.pop()
    allowed = (*spec.required, *spec.optional)
    if (
        any(header not in allowed for header in headers)
        or len(set(headers)) != len(headers)
        or any(header not in headers for header in spec.required)
    ):
        errors.append(row_error(worksheet.title, 1, {
            "header": [f"Use unique columns from {', '.join(allowed)}. Required: {', '.join(spec.required)}."]
        }))
        return []

    records = []
    refs = set()
    for row_number, cells in enumerate(rows, start=2):
        if row_number > MAX_ROWS_PER_SHEET + 1:
            errors.append(row_error(worksheet.title, row_number, {
                "row": [f"Use at most {MAX_ROWS_PER_SHEET} rows per sheet."]
            }))
            break
        if all(cell.value is None for cell in cells):
            continue

        values = {}
        problems = {}
        if any(cell.value is not None for cell in cells[len(headers):]):
            problems["row"] = ["Every value needs a column heading."]
        for header, cell in zip(headers, cells):
            if cell.value is None:
                continue
            if cell.data_type in {"f", "e"}:
                problems[header] = ["Use literal values without formulas or Excel errors."]
                continue
            if header in JSON_COLUMNS:
                try:
                    values[header] = json.loads(cell.value)
                except (TypeError, ValueError, RecursionError):
                    problems[header] = ["Enter valid JSON as text."]
            else:
                values[header] = cell.value

        ref = values.pop("ref", None)
        if ref is not None:
            if not isinstance(ref, str) or not REF_PATTERN.fullmatch(ref):
                problems["ref"] = ["Use 1 to 64 letters, digits, hyphens or underscores, starting with a letter or digit."]
            elif ref in refs:
                problems["ref"] = ["This reference already appears on the sheet."]
            else:
                refs.add(ref)

        if problems:
            errors.append(row_error(worksheet.title, row_number, problems))
        else:
            records.append((row_number, ref, values))
    return records


def read_workbook(upload):
    if not upload.name.lower().endswith(".xlsx") or upload.size > MAX_UPLOAD_BYTES:
        raise file_error("Upload an .xlsx workbook of up to 5 MiB.")
    try:
        with ZipFile(upload) as archive:
            entries = archive.infolist()
            if len(entries) > 200 or sum(item.file_size for item in entries) > MAX_EXPANDED_BYTES:
                raise file_error("The workbook expands beyond the import limit.")
            if any(item.filename.lower().endswith("/vbaproject.bin") for item in entries):
                raise file_error("Upload an .xlsx workbook without macros.")

        upload.seek(0)
        workbook = load_workbook(upload, read_only=True, data_only=False, keep_links=False)
        records = {}
        errors = []
        try:
            for worksheet in workbook.worksheets:
                if worksheet.title not in SHEETS:
                    errors.append(row_error(worksheet.title, None, {"sheet": ["Unknown worksheet."]}))
                    continue
                records[worksheet.title] = read_sheet(worksheet, SHEETS[worksheet.title], errors)
        finally:
            workbook.close()
    except (
        BadZipFile, InvalidFileException, ParseError, DefusedXmlException, OSError,
        ValueError, TypeError, KeyError, IndexError, RuntimeError, NotImplementedError, OverflowError,
    ):
        raise file_error("The file could not be read as an .xlsx workbook.") from None

    if errors:
        raise RejectedWorkbook(errors)
    if not any(records.values()):
        raise file_error("The workbook has no metadata rows.")
    return records


@transaction.atomic
def import_workbook(records, context):
    department_id = context["department_id"]
    lock_metadata_write(department_id)
    counts = {}
    references = {sheet: {} for sheet in REFERENCE_SHEETS.values()}
    errors = []

    for sheet, spec in SHEETS.items():
        if sheet not in records:
            continue
        counts[sheet] = 0
        for row_number, ref, fields in records[sheet]:
            data = dict(fields)
            problems = {}
            if sheet == "Measurements":
                for column, target in REFERENCE_SHEETS.items():
                    value = data.get(column)
                    if isinstance(value, str) and value.startswith("@"):
                        pk = references[target].get(value[1:])
                        if pk is None:
                            problems[column] = ["This workbook reference could not be resolved."]
                            data.pop(column)
                        else:
                            data[column] = pk

            serializer = spec.serializer(data=data, context=context)
            if not serializer.is_valid() or problems:
                errors.append(row_error(sheet, row_number, {**serializer.errors, **problems}))
                continue

            try:
                with transaction.atomic():
                    instance = serializer.save(
                        department_id=department_id,
                        created_by=context["request"].user,
                        updated_by=context["request"].user,
                    )
            except serializers.ValidationError as error:
                errors.append(row_error(sheet, row_number, error.detail))
                continue
            if ref is not None:
                references[sheet][ref] = instance.pk
            counts[sheet] += 1

    if errors:
        raise RejectedWorkbook(errors)
    return counts


class ImportRequestSerializer(DepartmentSelectionSerializer):
    file = serializers.FileField(max_length=255)


class MetadataImportView(DepartmentScope, APIView):
    parser_classes = (MultiPartParser,)

    def post(self, request):
        selection = ImportRequestSerializer(data=request.data)
        selection.is_valid(raise_exception=True)
        department_id = selection.validated_data["department"]
        self.require_writable_department(department_id)
        try:
            rows = read_workbook(selection.validated_data["file"])
            counts = import_workbook(rows, {
                "department_id": department_id,
                "platform_department_id": self.platform_department_id,
                "request": request,
            })
        except RejectedWorkbook as error:
            return Response({"errors": error.errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"created": counts}, status=status.HTTP_201_CREATED)
