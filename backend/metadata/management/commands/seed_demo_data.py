"""Fill a development database with demo Departments, catalogs and map data."""

import json

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from local_departments.models import Department, Organisation
from metadata.models import (
    ExternalIdentifier, Measurement, MeasurementType, MeasurementUnit, NetworkElement,
    NetworkElementType, PhysicalDevice, PhysicalDeviceType,
)
from metadata.platform import configured_platform_department_id
from platform_security.models import UserDepartment

DEVICE_TYPES = ["Weather station", "Flow meter", "Pressure sensor", "Water quality probe"]
ELEMENT_TYPES = ["Pipe", "Tank", "Junction", "Pumping station", "District metered area"]
MEASUREMENT_TYPES = ["Air temperature", "Flow rate", "Water pressure", "Water level", "Chlorine residual"]
UNITS = [("Celsius", "°C"), ("Cubic metres per hour", "m³/h"), ("Bar", "bar"), ("Metre", "m"), ("Milligrams per litre", "mg/L")]

# name -> (lon, lat) for devices; elements are (type, GeoJSON geometry, dma, strategic)
SITES = {
    "Nicosia": {
        "devices": [("NIC-FM-01", "Flow meter", 33.3823, 35.1856), ("NIC-PS-02", "Pressure sensor", 33.3650, 35.1700),
                    ("NIC-WS-03", "Weather station", 33.4010, 35.1620), ("NIC-WQ-04", "Water quality probe", 33.3560, 35.1810)],
        "elements": [
            ("Pumping station", {"type": "Point", "coordinates": [33.3830, 35.1850]}, "DMA-N1", "STR-N-PS1"),
            ("Junction", {"type": "Point", "coordinates": [33.3660, 35.1710]}, "DMA-N2", ""),
            ("Pipe", {"type": "LineString", "coordinates": [[33.3830, 35.1850], [33.3745, 35.1780], [33.3660, 35.1710]]}, "DMA-N1", "STR-N-P7"),
            ("Pipe", {"type": "LineString", "coordinates": [[33.3660, 35.1710], [33.3600, 35.1760], [33.3560, 35.1810]]}, "DMA-N2", "STR-N-P8"),
            ("Tank", {"type": "Polygon", "coordinates": [[[33.4000, 35.1610], [33.4030, 35.1610], [33.4030, 35.1635], [33.4000, 35.1635], [33.4000, 35.1610]]]}, "DMA-N3", "STR-N-T1"),
            ("District metered area", {"type": "Polygon", "coordinates": [[[33.3500, 35.1650], [33.3900, 35.1650], [33.3900, 35.1900], [33.3500, 35.1900], [33.3500, 35.1650]]]}, "DMA-N", ""),
        ],
    },
    "Limassol": {
        "devices": [("LIM-FM-01", "Flow meter", 33.0300, 34.6850), ("LIM-PS-02", "Pressure sensor", 33.0450, 34.6950),
                    ("LIM-WS-03", "Weather station", 33.0100, 34.7050), ("LIM-WQ-04", "Water quality probe", 33.0560, 34.6720)],
        "elements": [
            ("Pumping station", {"type": "Point", "coordinates": [33.0310, 34.6840]}, "DMA-L1", "STR-L-PS1"),
            ("Junction", {"type": "Point", "coordinates": [33.0455, 34.6955]}, "DMA-L2", ""),
            ("Pipe", {"type": "LineString", "coordinates": [[33.0310, 34.6840], [33.0380, 34.6900], [33.0455, 34.6955]]}, "DMA-L1", "STR-L-P3"),
            ("Tank", {"type": "Polygon", "coordinates": [[[33.0090, 34.7040], [33.0120, 34.7040], [33.0120, 34.7065], [33.0090, 34.7065], [33.0090, 34.7040]]]}, "DMA-L3", "STR-L-T2"),
            ("District metered area", {"type": "Polygon", "coordinates": [[[33.0200, 34.6700], [33.0600, 34.6700], [33.0600, 34.7000], [33.0200, 34.7000], [33.0200, 34.6700]]]}, "DMA-L", ""),
        ],
    },
}
DEVICE_MEASUREMENT = {"Flow meter": ("Flow rate", "Cubic metres per hour"), "Pressure sensor": ("Water pressure", "Bar"),
                      "Weather station": ("Air temperature", "Celsius"), "Water quality probe": ("Chlorine residual", "Milligrams per litre")}


class Command(BaseCommand):
    help = "Create demo Departments, catalogs, devices, network elements (points, lines, polygons) and measurements. Safe to re-run."

    def add_arguments(self, parser):
        parser.add_argument("--member", default="", help="Username to add to the demo Departments (default: every existing user).")

    @transaction.atomic
    def handle(self, *args, member="", **options):
        platform_id = configured_platform_department_id()
        if platform_id is None or not Department.objects.filter(pk=platform_id).exists():
            raise CommandError("Set METADATA_PLATFORM_DEPARTMENT_ID to an existing Platform Department first.")
        users = get_user_model().objects.filter(username=member) if member else get_user_model().objects.all()
        if member and not users.exists():
            raise CommandError("That user does not exist.")
        actor = users.first()
        stamp = {"created_by": actor, "updated_by": actor}

        def entry(model, name, **extra):
            return model.objects.get_or_create(department_id=platform_id, name=name, defaults={**stamp, **extra})[0]

        device_types = {n: entry(PhysicalDeviceType, n) for n in DEVICE_TYPES}
        element_types = {n: entry(NetworkElementType, n) for n in ELEMENT_TYPES}
        m_types = {n: entry(MeasurementType, n) for n in MEASUREMENT_TYPES}
        units = {n: entry(MeasurementUnit, n, symbol=s) for n, s in UNITS}

        organisation, _ = Organisation.objects.get_or_create(code="cyprus-water", defaults={"name": "Cyprus Water Authority"})
        created = {"devices": 0, "elements": 0, "measurements": 0}
        for dept_name, spec in SITES.items():
            department, _ = Department.objects.get_or_create(organisation=organisation, name=dept_name)
            for user in users:
                UserDepartment.objects.get_or_create(user=user, department=department)
            scope = {"department": department}

            elements = []
            for index, (kind, geometry, dma, strategic) in enumerate(spec["elements"], 1):
                name = f"{dept_name} {kind} {index:02d}"
                element, new = NetworkElement.objects.get_or_create(
                    name=name, **scope, defaults={
                        **stamp, "element_type": element_types[kind], "dma_model_id": dma, "strategic_model_id": strategic,
                        "geometry": GEOSGeometry(json.dumps(geometry), srid=4326),
                        "description": f"Demo {kind.lower()} in {dept_name}.",
                    })
                if new:
                    created["elements"] += 1
                    ExternalIdentifier.objects.create(
                        network_element=element, source="GIS", value=f"{dept_name[:3].upper()}-{index:03d}",
                        created_by=actor, updated_by=actor,
                    )
                elements.append(element)

            for index, (code, kind, lon, lat) in enumerate(spec["devices"]):
                device, new = PhysicalDevice.objects.get_or_create(
                    name=code, **scope, defaults={
                        **stamp, "device_type": device_types[kind], "location": GEOSGeometry(f"POINT({lon} {lat})", srid=4326),
                        "description": f"Demo {kind.lower()} in {dept_name}.",
                    })
                if new:
                    created["devices"] += 1
                type_name, unit_name = DEVICE_MEASUREMENT[kind]
                element = elements[index % len(elements)]
                _, new = Measurement.objects.get_or_create(
                    name=f"{code} {type_name}", **scope, defaults={
                        **stamp, "physical_device": device, "network_element": element,
                        "measurement_type": m_types[type_name], "measurement_unit": units[unit_name],
                        "customer_account": f"CUST-{dept_name[:3].upper()}-{index + 1:04d}",
                        "meter_account": f"METER-{code}",
                        "data_collection_config": {
                            "protocol": "https", "endpoint": f"https://scada.example.invalid/{code.lower()}",
                            "source_identifier": code, "extra_settings": {"interval_seconds": 60 * (index + 1)},
                        },
                    })
                if new:
                    created["measurements"] += 1
        self.stdout.write(f"Created {created['devices']} devices, {created['elements']} network elements, "
                          f"{created['measurements']} measurements. Existing demo rows were left untouched.")
