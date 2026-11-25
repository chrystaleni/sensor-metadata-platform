"""Export one Department as a workbook in the client's layout (``EXCEL-317.xlsx``).

The workbook has the same ``Measurements``, ``NetworkElements`` and ``Physical_devices``
worksheets and column headings that :mod:`metadata.client_format` imports, so an
exported file can be opened next to the client's own workbook and imported again.
The extra lookup columns of the client's Measurements sheet (NetworkElementName,
SensorStationName, ...) are written as plain values instead of VLOOKUP formulas;
the import ignores them.
"""

from io import BytesIO
import json

from django.apps import apps
from django.conf import settings
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView

from .models import Measurement, NetworkElement, PhysicalDevice
from .serializers import DepartmentSelectionSerializer
from .views import DepartmentScope

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

MEASUREMENT_COLUMNS = (
    "Department", "MeasurementId", "MeasurementName", "MeasurementCollectionBatch", "MeasurementType",
    "Meter Account", "Customer Account", "MeasurementUnit", "Details", "NetworkElementId",
    "NetworkElementName", "NetworkElementType", "NetworkArea", "Latitude", "Longitude", "Elevation",
    "StrategicId", "DMAId", "PhysicalDeviceId", "SensorStationName", "SensorStationType",
    "DataCollectionType", "DataCollectionParameters",
)
ELEMENT_COLUMNS = (
    "Department", "NetworkElementId", "NetworkElementName", "NetworkElementType", "NetworkArea",
    "Latitude", "Longitude", "Elevation", "StrategicId", "DMAId", "Address",
)
DEVICE_COLUMNS = (
    "Department", "Device_id", "Device_name", "Device_type", "CommunicationParameters", "longitude", "latitude",
)
# Keys of a collection configuration that have their own Measurements column.
MAPPED_CONFIG_KEYS = {"source_identifier", "protocol", "collection_batch", "extra_settings"}


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")) if value else None


def _point(geometry):
    """(longitude, latitude) of a Point geometry; other shapes have no single position."""
    if geometry is not None and geometry.geom_type == "Point":
        return geometry.x, geometry.y
    return None, None


def _blank(value):
    return value if value not in ("", None) else None


def device_ids(devices):
    """The client's Device_id of each device: the imported ID, else the name, made unique."""
    result, used = {}, set()
    for device in devices:
        description = device.description or ""
        candidate = description[len("Device ID: "):].strip() if description.startswith("Device ID: ") else device.name
        if not candidate or candidate.lower() in used:
            candidate = f"DEVICE-{device.pk}"
        used.add(candidate.lower())
        result[device.pk] = candidate
    return result


def element_ids(elements):
    """The client's NetworkElementId: the imported identifier, else the first one, made unique."""
    result, used = {}, set()
    for element in elements:
        identifiers = list(element.active_external_identifiers)
        preferred = [i.value for i in identifiers if i.source == "NetworkElementId"] or [i.value for i in identifiers]
        candidate = preferred[0] if preferred else None
        if not candidate or candidate.lower() in used:
            candidate = f"NE-{element.pk}"
        used.add(candidate.lower())
        result[element.pk] = candidate
    return result


def _sheet(workbook, title, columns, rows, frozen):
    sheet = workbook.create_sheet(title)
    sheet.append(columns)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = frozen
    sheet.auto_filter.ref = sheet.dimensions
    for index, column in enumerate(columns, start=1):
        width = max([len(str(column))] + [len(str(row[index - 1])) for row in rows if row[index - 1] is not None])
        sheet.column_dimensions[get_column_letter(index)].width = min(max(width + 2, 10), 60)


def build_workbook(department):
    devices = list(
        PhysicalDevice.objects.active().filter(department_id=department.pk).select_related("device_type").order_by("id")
    )
    elements = list(
        NetworkElement.objects.active().filter(department_id=department.pk)
        .select_related("element_type").prefetch_related("external_identifiers").order_by("id")
    )
    for element in elements:
        element._prefetched_active_identifiers = [
            i for i in element.external_identifiers.all() if i.deleted_at is None
        ]
    measurements = list(
        Measurement.objects.active().filter(department_id=department.pk)
        .select_related("physical_device__device_type", "network_element__element_type",
                        "measurement_type", "measurement_unit", "collection_configuration")
        .order_by("id")
    )
    device_id, element_id = device_ids(devices), element_ids(elements)
    department_name = department.name

    def element_values(element):
        lon, lat = _point(element.geometry)
        return {
            "NetworkElementName": element.name, "NetworkElementType": element.element_type.name,
            "NetworkArea": _blank(element.network_area), "Latitude": lat, "Longitude": lon,
            "Elevation": element.elevation, "StrategicId": _blank(element.strategic_model_id),
            "DMAId": _blank(element.dma_model_id), "Address": _blank(element.address),
        }

    element_rows = []
    for element in elements:
        values = {"Department": department_name, "NetworkElementId": element_id[element.pk], **element_values(element)}
        element_rows.append([values.get(column) for column in ELEMENT_COLUMNS])

    device_rows = []
    for device in devices:
        lon, lat = _point(device.location)
        device_rows.append([department_name, device_id[device.pk], device.name, device.device_type.name,
                            _json(device.communication_parameters), lon, lat])

    measurement_rows = []
    for measurement in measurements:
        configuration = getattr(measurement, "collection_configuration", None)
        config = dict(configuration.config) if configuration is not None and isinstance(configuration.config, dict) else {}
        # Unmapped keys (for example "endpoint") travel with the parameters so nothing is lost.
        extra = config.get("extra_settings") if isinstance(config.get("extra_settings"), dict) else {}
        parameters = {**extra, **{k: v for k, v in config.items() if k not in MAPPED_CONFIG_KEYS}}
        element, device = measurement.network_element, measurement.physical_device
        values = {
            "Department": department_name,
            "MeasurementId": config.get("source_identifier"),
            "MeasurementName": measurement.name,
            "MeasurementCollectionBatch": config.get("collection_batch"),
            "MeasurementType": measurement.measurement_type.name,
            "Meter Account": _blank(measurement.meter_account),
            "Customer Account": _blank(measurement.customer_account),
            "MeasurementUnit": measurement.measurement_unit.name,
            "Details": _blank(measurement.description),
            "NetworkElementId": element_id.get(element.pk, f"NE-{element.pk}"),
            **element_values(element),
            "PhysicalDeviceId": device_id.get(device.pk, f"DEVICE-{device.pk}"),
            "SensorStationName": device.name,
            "SensorStationType": device.device_type.name,
            "DataCollectionType": config.get("protocol"),
            "DataCollectionParameters": _json(parameters),
        }
        measurement_rows.append([values.get(column) for column in MEASUREMENT_COLUMNS])

    workbook = Workbook()
    workbook.remove(workbook.active)
    _sheet(workbook, "Measurements", MEASUREMENT_COLUMNS, measurement_rows, "D2")
    _sheet(workbook, "NetworkElements", ELEMENT_COLUMNS, element_rows, "C2")
    _sheet(workbook, "Physical_devices", DEVICE_COLUMNS, device_rows, "C2")
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


class MetadataExportView(DepartmentScope, APIView):
    def get(self, request):
        selection = DepartmentSelectionSerializer(data=request.query_params)
        selection.is_valid(raise_exception=True)
        department_id = selection.validated_data["department"]
        if department_id not in self.access_policy.readable_department_ids(request):
            raise PermissionDenied("You do not have read access to this department.")
        department = apps.get_model(settings.METADATA_DEPARTMENT_MODEL).objects.filter(pk=department_id).first()
        if department is None:
            raise serializers.ValidationError({"department": ["Unknown department."]})
        filename = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in department.name) or "department"
        response = HttpResponse(build_workbook(department), content_type=XLSX)
        response["Content-Disposition"] = f'attachment; filename="Sensor_Metadata_{filename}.xlsx"'
        return response
