"""Import of the client's own workbook layout (``EXCEL-317.xlsx``).

The client keeps its metadata in three worksheets that refer to each other by
the client's own identifiers and describe controlled-list values by *name*:

``Measurements``      MeasurementId, MeasurementName, MeasurementCollectionBatch,
                      MeasurementType, Meter Account, Customer Account,
                      MeasurementUnit, Details, NetworkElementId, PhysicalDeviceId,
                      DataCollectionType, DataCollectionParameters
``NetworkElements``   NetworkElementId, NetworkElementName, NetworkElementType,
                      NetworkArea, Latitude, Longitude, Elevation, StrategicId, DMAId, Address
``Physical_devices``  Device_id, Device_name, Device_type, CommunicationParameters,
                      longitude, latitude

Every other column (including the spreadsheet formulas that merely look values up
in another sheet) and the ``Statistics``, ``LOVs`` and ``Structure`` sheets are
ignored. The first column, ``Department``, is informational: records go to the
Department chosen in the upload form.

This module only translates. The translated rows then go through the normal
serializers and the same atomic import as the platform's own template, so every
validation, Department-ownership and uniqueness rule still applies.
"""

import re

from rest_framework.utils import json

from .access import get_access_policy
from .models import MeasurementType, MeasurementUnit, NetworkElementType, PhysicalDeviceType
from .writes import lock_metadata_write

MAX_ROWS_PER_SHEET = 2000

# worksheet -> (internal sheet name used by import_workbook, required columns, optional columns)
CLIENT_SHEETS = {
    "Physical_devices": ("Physical Devices",
                         ("Device_id", "Device_name", "Device_type"),
                         ("Department", "CommunicationParameters", "longitude", "latitude")),
    "NetworkElements": ("Network Elements",
                        ("NetworkElementId", "NetworkElementName", "NetworkElementType"),
                        ("Department", "NetworkArea", "Latitude", "Longitude", "Elevation", "StrategicId", "DMAId", "Address")),
    "Measurements": ("Measurements",
                     ("MeasurementName", "MeasurementType", "MeasurementUnit", "NetworkElementId", "PhysicalDeviceId"),
                     ("Department", "MeasurementId", "MeasurementCollectionBatch", "Meter Account", "Customer Account",
                      "Details", "DataCollectionType", "DataCollectionParameters")),
}
IGNORED_SHEETS = {"Statistics", "LOVs", "Structure"}
INTERNAL_TO_CLIENT_SHEET = {internal: client for client, (internal, _, _) in CLIENT_SHEETS.items()}

# Field names in error messages are translated back to the client's column headings.
FIELD_TO_COLUMN = {
    "Physical Devices": {"name": "Device_name", "device_type": "Device_type", "location": "longitude/latitude",
                         "communication_parameters": "CommunicationParameters"},
    "Network Elements": {"name": "NetworkElementName", "element_type": "NetworkElementType", "geometry": "Latitude/Longitude",
                         "external_identifiers": "NetworkElementId", "dma_model_id": "DMAId", "strategic_model_id": "StrategicId",
                         "network_area": "NetworkArea", "elevation": "Elevation", "address": "Address"},
    "Measurements": {"name": "MeasurementName", "physical_device": "PhysicalDeviceId", "network_element": "NetworkElementId",
                     "measurement_type": "MeasurementType", "measurement_unit": "MeasurementUnit", "description": "Details",
                     "data_collection_config": "DataCollectionType / DataCollectionParameters",
                     "customer_account": "Customer Account", "meter_account": "Meter Account"},
}


class ClientWorkbook(dict):
    """Rows read from the client layout, still holding names instead of catalog IDs."""


def _norm(header):
    return re.sub(r"[\s_]+", "", str(header)).lower() if header is not None else ""


def is_client_layout(worksheets):
    titles = {ws.title for ws in worksheets}
    if titles & {"NetworkElements", "Physical_devices"}:
        return True
    for ws in worksheets:
        if ws.title == "Measurements":
            ws.reset_dimensions()
            first = next(ws.iter_rows(max_row=1), ())
            return any(_norm(c.value) == "measurementid" for c in first)
    return False


def _text(value):
    """Cell value as trimmed text; whole numbers lose their '.0'."""
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    value = str(value).strip()
    return value or None


def _number(value, label, problems, key):
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return float(value)
    except (TypeError, ValueError):
        problems.setdefault(key, []).append(f"{label} must be a number.")
        return None


def _json_object(value, label, problems, key):
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, RecursionError):
        problems.setdefault(key, []).append(f"{label} must be valid JSON text.")
        return None
    if not isinstance(parsed, dict):
        problems.setdefault(key, []).append(f"{label} must be a JSON object, for example {{\"IP\":\"10.0.0.1\"}}.")
        return None
    return parsed


def _point(lon, lat, problems, key, lon_label, lat_label):
    if lon is None and lat is None:
        return None
    if lon is None or lat is None:
        problems.setdefault(key, []).append(f"Provide both {lon_label} and {lat_label}, or neither.")
        return None
    return {"type": "Point", "coordinates": [lon, lat]}


def read_client_sheets(workbook, errors, row_error):
    """Read the three client worksheets into raw (row, values) lists; problems go to ``errors``."""
    raw = ClientWorkbook()
    for ws in workbook.worksheets:
        if ws.title in IGNORED_SHEETS:
            continue
        if ws.title not in CLIENT_SHEETS:
            errors.append(row_error(ws.title, None, {"sheet": [
                "Unknown worksheet. Expected Measurements, NetworkElements and Physical_devices."]}))
            continue
        _, required, optional = CLIENT_SHEETS[ws.title]
        ws.reset_dimensions()
        rows = ws.iter_rows()
        headers = [c.value for c in next(rows, ())]
        index = {}
        for position, header in enumerate(headers):
            index.setdefault(_norm(header), position)
        wanted = {name: index.get(_norm(name)) for name in (*required, *optional)}
        missing = [name for name in required if wanted[name] is None]
        if missing:
            errors.append(row_error(ws.title, 1, {"header": [f"Missing required column(s): {', '.join(missing)}."]}))
            continue
        records = []
        for row_number, cells in enumerate(rows, start=2):
            if row_number > MAX_ROWS_PER_SHEET + 1:
                errors.append(row_error(ws.title, row_number, {"row": [f"Use at most {MAX_ROWS_PER_SHEET} rows per sheet."]}))
                break
            values, problems = {}, {}
            for name, position in wanted.items():
                if position is None or position >= len(cells):
                    continue
                cell = cells[position]
                if cell.value is None:
                    continue
                if cell.data_type in {"f", "e"}:
                    problems[name] = ["Use a literal value, not a formula or Excel error."]
                    continue
                values[name] = cell.value
            if not any(v is not None for v in (_text(v) if not isinstance(v, (int, float)) else v for v in values.values())):
                continue
            if problems:
                errors.append(row_error(ws.title, row_number, problems))
            else:
                records.append((row_number, values))
        raw[ws.title] = records
    return raw


def _lookup(model, platform_id):
    return {e.name.lower(): e for e in model.objects.active().filter(department_id=platform_id)} if platform_id else {}


def resolve_client_records(raw, context, row_error, reject):
    """Translate raw client rows into the platform's import records.

    Controlled-list names that do not exist yet are created in the shared Platform
    lists when the importing user may manage those lists; otherwise the affected
    rows are rejected. Must run inside the import transaction.
    """
    request, platform_id = context["request"], context.get("platform_department_id")
    can_create = bool(platform_id) and get_access_policy().can_manage_controlled_lists(request)
    errors = []

    # Collect and clean every row first so problems are reported together.
    devices, elements, measurements = [], [], []
    names = {"device_type": {}, "element_type": {}, "measurement_type": {}, "measurement_unit": {}}

    def want(kind, value):
        text = _text(value)
        if text:
            names[kind].setdefault(text.lower(), text)
        return text

    seen_devices, seen_elements = {}, {}
    for row, v in raw.get("Physical_devices", []):
        problems = {}
        device_id, name = _text(v.get("Device_id")), _text(v.get("Device_name"))
        for key, value in (("Device_id", device_id), ("Device_name", name), ("Device_type", _text(v.get("Device_type")))):
            if value is None:
                problems[key] = ["This value is required."]
        if device_id and device_id.lower() in seen_devices:
            problems["Device_id"] = ["This Device_id already appears on the sheet."]
        fields = {"name": name}
        description = None if device_id == name else (f"Device ID: {device_id}" if device_id else None)
        if description:
            fields["description"] = description
        lon = _number(v.get("longitude"), "longitude", problems, "longitude")
        lat = _number(v.get("latitude"), "latitude", problems, "latitude")
        point = _point(lon, lat, problems, "longitude", "longitude", "latitude")
        if point:
            fields["location"] = point
        params = _json_object(v.get("CommunicationParameters"), "CommunicationParameters", problems, "CommunicationParameters")
        if params is not None:
            fields["communication_parameters"] = params
        kind = want("device_type", v.get("Device_type"))
        if problems:
            errors.append(row_error("Physical_devices", row, problems))
            continue
        seen_devices[device_id.lower()] = f"d{len(devices)}"
        devices.append((row, seen_devices[device_id.lower()], fields, ("device_type", kind)))

    for row, v in raw.get("NetworkElements", []):
        problems = {}
        element_id, name = _text(v.get("NetworkElementId")), _text(v.get("NetworkElementName"))
        for key, value in (("NetworkElementId", element_id), ("NetworkElementName", name),
                           ("NetworkElementType", _text(v.get("NetworkElementType")))):
            if value is None:
                problems[key] = ["This value is required."]
        if element_id and element_id.lower() in seen_elements:
            problems["NetworkElementId"] = ["This NetworkElementId already appears on the sheet."]
        fields = {"name": name, "external_identifiers": [{"source": "NetworkElementId", "value": element_id}] if element_id else []}
        lon = _number(v.get("Longitude"), "Longitude", problems, "Longitude")
        lat = _number(v.get("Latitude"), "Latitude", problems, "Latitude")
        point = _point(lon, lat, problems, "Latitude", "Longitude", "Latitude")
        if point:
            fields["geometry"] = point
        elevation = _number(v.get("Elevation"), "Elevation", problems, "Elevation")
        if elevation is not None:
            fields["elevation"] = elevation
        for column, field in (("DMAId", "dma_model_id"), ("StrategicId", "strategic_model_id"),
                              ("NetworkArea", "network_area"), ("Address", "address")):
            text = _text(v.get(column))
            if text is not None:
                fields[field] = text
        kind = want("element_type", v.get("NetworkElementType"))
        if problems:
            errors.append(row_error("NetworkElements", row, problems))
            continue
        seen_elements[element_id.lower()] = f"n{len(elements)}"
        elements.append((row, seen_elements[element_id.lower()], fields, ("element_type", kind)))

    for row, v in raw.get("Measurements", []):
        problems = {}
        fields = {"name": _text(v.get("MeasurementName"))}
        if fields["name"] is None:
            problems["MeasurementName"] = ["This value is required."]
        device_ref = seen_devices.get((_text(v.get("PhysicalDeviceId")) or "").lower())
        element_ref = seen_elements.get((_text(v.get("NetworkElementId")) or "").lower())
        if device_ref is None:
            problems["PhysicalDeviceId"] = [
                f"'{_text(v.get('PhysicalDeviceId')) or ''}' is not a valid Device_id on the Physical_devices sheet."]
        if element_ref is None:
            problems["NetworkElementId"] = [
                f"'{_text(v.get('NetworkElementId')) or ''}' is not a valid NetworkElementId on the NetworkElements sheet."]
        fields["physical_device"], fields["network_element"] = f"@{device_ref}", f"@{element_ref}"
        type_name = want("measurement_type", v.get("MeasurementType"))
        unit_name = want("measurement_unit", v.get("MeasurementUnit"))
        for key, value in (("MeasurementType", type_name), ("MeasurementUnit", unit_name)):
            if value is None:
                problems[key] = ["This value is required."]
        for column, field in (("Details", "description"), ("Customer Account", "customer_account"), ("Meter Account", "meter_account")):
            text = _text(v.get(column))
            if text is not None:
                fields[field] = text
        config = {}
        source = _text(v.get("MeasurementId"))
        if source:
            config["source_identifier"] = source
        protocol = _text(v.get("DataCollectionType"))
        if protocol:
            config["protocol"] = protocol
        params = _json_object(v.get("DataCollectionParameters"), "DataCollectionParameters", problems, "DataCollectionParameters")
        if params:
            config["extra_settings"] = params
        batch = _text(v.get("MeasurementCollectionBatch"))
        if batch is not None:
            config["collection_batch"] = int(batch) if batch.isdigit() else batch
        if config:
            fields["data_collection_config"] = config
        if problems:
            errors.append(row_error("Measurements", row, problems))
            continue
        measurements.append((row, None, fields, (("measurement_type", type_name), ("measurement_unit", unit_name))))

    if errors:
        raise reject(errors)

    # Resolve controlled-list names, creating the missing ones when permitted.
    models = {"device_type": PhysicalDeviceType, "element_type": NetworkElementType,
              "measurement_type": MeasurementType, "measurement_unit": MeasurementUnit}
    labels = {"device_type": "Device_type", "element_type": "NetworkElementType",
              "measurement_type": "MeasurementType", "measurement_unit": "MeasurementUnit"}
    sheets_of = {"device_type": "Physical_devices", "element_type": "NetworkElements",
                 "measurement_type": "Measurements", "measurement_unit": "Measurements"}
    existing = {kind: _lookup(model, platform_id) for kind, model in models.items()}
    missing = {kind: [n for low, n in found.items() if low not in existing[kind]] for kind, found in names.items()}
    created = 0
    if any(missing.values()):
        if not can_create:
            for kind, wanted in missing.items():
                for name in wanted:
                    errors.append(row_error(sheets_of[kind], None, {labels[kind]: [
                        f"'{name}' is not in the shared lists. Ask a System Administrator to add it, "
                        "or have one run this import."]}))
            raise reject(errors)
        lock_metadata_write(platform_id, controlled_list=True)
        for kind, wanted in missing.items():
            for name in wanted:
                extra = {"symbol": name[:24]} if kind == "measurement_unit" else {}
                entry = models[kind].objects.create(
                    department_id=platform_id, name=name, created_by=request.user, updated_by=request.user, **extra)
                existing[kind][name.lower()] = entry
                created += 1

    def pk(kind, name):
        return existing[kind][name.lower()].pk

    records = {}
    records["Physical Devices"] = [(row, ref, {**fields, "device_type": pk(*kind)}) for row, ref, fields, kind in devices]
    records["Network Elements"] = [(row, ref, {**fields, "element_type": pk(*kind)}) for row, ref, fields, kind in elements]
    records["Measurements"] = [
        (row, ref, {**fields, "measurement_type": pk(*kinds[0]), "measurement_unit": pk(*kinds[1])})
        for row, ref, fields, kinds in measurements]
    return records, created


def client_errors(errors):
    """Rename internal sheet and field names in import errors to the client's own headings."""
    renamed = []
    for item in errors:
        sheet = item.get("sheet")
        columns = FIELD_TO_COLUMN.get(sheet, {})
        renamed.append({**item, "sheet": INTERNAL_TO_CLIENT_SHEET.get(sheet, sheet),
                        "errors": ({columns.get(k, k): v for k, v in item["errors"].items()}
                                if isinstance(item["errors"], dict) else item["errors"])})
    return renamed


def client_counts(counts, created_entries):
    result = {INTERNAL_TO_CLIENT_SHEET.get(sheet, sheet): n for sheet, n in counts.items()}
    result["New shared list entries"] = created_entries
    return result
