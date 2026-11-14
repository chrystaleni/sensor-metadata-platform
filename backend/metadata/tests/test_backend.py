from concurrent.futures import ThreadPoolExecutor
from io import BytesIO, StringIO
from queue import Queue
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPoint, Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, connection, connections, transaction
from django.db.models.deletion import ProtectedError
from django.test import override_settings
from openpyxl import Workbook
from rest_framework.test import APIClient, APITestCase, APITransactionTestCase

from local_departments.models import Department

from ..access import NoAccessPolicy
from ..models import (
    ExternalIdentifier,
    Measurement,
    MeasurementType,
    MeasurementUnit,
    NetworkElement,
    NetworkElementType,
    PhysicalDevice,
    PhysicalDeviceType,
)


API = "/api/v1/"
pytestmark = pytest.mark.postgis
POLICY = "metadata.tests.test_backend.FixturePolicy"
POINT = {"type": "Point", "coordinates": [33.36, 35.15]}
LINE = {"type": "LineString", "coordinates": [[33.36, 35.15], [33.37, 35.16]]}
POLYGON = {
    "type": "Polygon",
    "coordinates": [[[33.36, 35.15], [33.37, 35.15], [33.37, 35.16], [33.36, 35.15]]],
}


class FixturePolicy(NoAccessPolicy):
    def readable_department_ids(self, request):
        return {"editor": (2,), "viewer": (2,), "multi": (2, 3)}.get(request.user.get_username(), ())

    def writable_department_ids(self, request):
        return {"editor": (2,), "multi": (2, 3)}.get(request.user.get_username(), ())

    def can_manage_controlled_lists(self, request):
        return request.user.get_username() == "catalog-manager"


def create_catalog():
    Department.objects.create(pk=1, name="Platform")
    Department.objects.create(pk=2, name="North")
    Department.objects.create(pk=3, name="South")
    return {
        "device_type": PhysicalDeviceType.objects.create(department_id=1, name="Weather station").pk,
        "element_type": NetworkElementType.objects.create(department_id=1, name="Monitoring site").pk,
        "measurement_type": MeasurementType.objects.create(department_id=1, name="Air temperature").pk,
        "measurement_unit": MeasurementUnit.objects.create(department_id=1, name="Celsius", symbol="°C").pk,
    }


def make_workbook(sheets):
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return SimpleUploadedFile("metadata.xlsx", output.getvalue())


@override_settings(METADATA_ACCESS_POLICY=POLICY, METADATA_PLATFORM_DEPARTMENT_ID=1)
class MetadataAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catalog = create_catalog()
        users = get_user_model().objects
        cls.editor = users.create_user(username="editor")
        cls.viewer = users.create_user(username="viewer")
        cls.manager = users.create_user(username="catalog-manager")
        cls.multi = users.create_user(username="multi")

    def setUp(self):
        self.client.force_authenticate(self.editor)

    def post(self, resource, data):
        return self.client.post(f"{API}{resource}/", data, format="json")

    def detail(self, resource, pk):
        return f"{API}{resource}/{pk}/"

    def device(self, department=2, name="Station A"):
        return PhysicalDevice.objects.create(
            department_id=department, name=name, device_type_id=self.catalog["device_type"]
        )

    def element(self, department=2, name="Site A"):
        return NetworkElement.objects.create(
            department_id=department, name=name, element_type_id=self.catalog["element_type"]
        )

    def measurement_data(self, device, element, department=2):
        return {
            "department": department,
            "name": "Outside temperature",
            "physical_device": device.pk,
            "network_element": element.pk,
            "measurement_type": self.catalog["measurement_type"],
            "measurement_unit": self.catalog["measurement_unit"],
        }

    def upload(self, sheets, department=2):
        return self.client.post(
            f"{API}imports/excel/",
            {"department": department, "file": make_workbook(sheets)},
            format="multipart",
        )

    def workbook_sheets(self, measurement_type=None):
        return {
            "Measurements": [
                ("name", "physical_device", "network_element", "measurement_type", "measurement_unit"),
                ("Imported measurement", "@station", "@site",
                 self.catalog["measurement_type"] if measurement_type is None else measurement_type,
                 self.catalog["measurement_unit"]),
            ],
            "Physical Devices": [
                ("ref", "name", "device_type", "location"),
                ("station", "Imported device", self.catalog["device_type"],
                 '{"type": "Point", "coordinates": [33.36, 35.15]}'),
            ],
            "Network Elements": [
                ("ref", "name", "element_type", "external_identifiers"),
                ("site", "Imported network element", self.catalog["element_type"],
                 '[{"source": "KIOS", "value": "SITE-101"}]'),
            ],
        }

    def test_linked_crud_archival_and_dependencies(self):
        device_response = self.post("physical-devices", {
            "department": 2, "name": "Weather station", "device_type": self.catalog["device_type"],
            "location": POINT,
        })
        self.assertEqual(device_response.status_code, 201, device_response.data)
        device = PhysicalDevice.objects.get(pk=device_response.data["id"])
        self.assertEqual(device.location.srid, 4326)
        self.assertEqual(self.client.get(self.detail("physical-devices", device.pk)).json()["location"], POINT)
        self.assertEqual(self.client.patch(
            self.detail("physical-devices", device.pk), {"name": "Roof station"}, format="json",
        ).status_code, 200)

        element_response = self.post("network-elements", {
            "department": 2, "name": "Monitoring area", "element_type": self.catalog["element_type"],
            "geometry": POLYGON, "external_identifiers": [{"source": "KIOS", "value": "A-1"}],
        })
        self.assertEqual(element_response.status_code, 201, element_response.data)
        element = NetworkElement.objects.get(pk=element_response.data["id"])
        self.assertEqual(element.geometry.srid, 4326)
        self.assertEqual(self.client.patch(
            self.detail("network-elements", element.pk), {"geometry": LINE}, format="json",
        ).json()["geometry"], LINE)

        data = self.measurement_data(device, element)
        data["data_collection_config"] = {"interval_seconds": 60}
        measurement_response = self.post("measurements", data)
        self.assertEqual(measurement_response.status_code, 201, measurement_response.data)
        pk = measurement_response.data["id"]
        path = self.detail("measurements", pk)
        self.assertEqual(self.client.get(path).json()["data_collection_config"], {"interval_seconds": 60})
        data["name"] = "Corrected measurement"
        self.assertEqual(self.client.put(path, data, format="json").json()["name"], data["name"])

        for resource, item in (("physical-devices", device), ("network-elements", element)):
            self.assertEqual(self.client.delete(self.detail(resource, item.pk)).status_code, 409)
        self.client.force_authenticate(self.manager)
        for resource, key in (("measurement-types", "measurement_type"), ("measurement-units", "measurement_unit"),
                              ("physical-device-types", "device_type"), ("network-element-types", "element_type")):
            self.assertEqual(self.client.delete(self.detail(resource, self.catalog[key])).status_code, 409)

        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.delete(path).status_code, 204)
        measurement = Measurement.objects.get(pk=pk)
        self.assertEqual(measurement.deleted_by_id, self.editor.pk)
        self.assertIsNotNone(measurement.deleted_at)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get(f"{API}measurements/").json()["count"], 0)
        self.assertEqual(self.client.delete(path).status_code, 404)
        self.assertEqual(self.client.delete(self.detail("network-elements", element.pk)).status_code, 204)
        self.assertEqual(self.client.delete(self.detail("physical-devices", device.pk)).status_code, 204)
        self.assertEqual(ExternalIdentifier.objects.get(network_element=element).deleted_by_id, self.editor.pk)
        with self.assertRaises(ProtectedError):
            device.delete()

        self.client.force_authenticate(self.manager)
        path = self.detail("measurement-types", self.catalog["measurement_type"])
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_required_relationships_and_non_integer_ids(self):
        response = self.post("measurements", {"department": 2, "name": "Incomplete"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"physical_device", "network_element", "measurement_type", "measurement_unit"})

        data = self.measurement_data(self.device(), self.element())
        data["physical_device"] += 0.5
        response = self.post("measurements", data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("physical_device", response.data)
        self.assertFalse(Measurement.objects.exists())

    def test_authorization_scopes_detail_search_create_and_relations(self):
        device = self.device(department=3, name="South private station")
        element = self.element()
        path = self.detail("physical-devices", device.pk)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.patch(path, {"name": "Changed"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(path).status_code, 404)
        self.assertEqual(self.client.get(f"{API}physical-devices/?search=South").json()["count"], 0)
        self.assertEqual(self.client.get(f"{API}physical-devices/?department=3").json()["count"], 0)
        response = self.post("physical-devices", {
            "department": 3, "name": "Blocked", "device_type": self.catalog["device_type"],
        })
        self.assertEqual(response.status_code, 403)
        response = self.post("measurements", self.measurement_data(device, element))
        self.assertEqual(response.status_code, 400)
        self.assertIn("physical_device", response.data)
        self.client.force_authenticate(self.multi)
        self.assertEqual(self.client.get(path).status_code, 200)
        response = self.client.patch(path, {"department": 2}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("department", response.data)

    def test_read_only_department_cannot_write(self):
        device = self.device()
        path = self.detail("physical-devices", device.pk)
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.patch(path, {"name": "Blocked"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(path).status_code, 404)
        self.assertEqual(self.upload(self.workbook_sheets()).status_code, 403)

    def test_measurement_and_network_detail_operations_keep_department_scope(self):
        device, element = self.device(department=3), self.element(department=3)
        measurement = Measurement.objects.create(
            department_id=3, name="Private measurement", physical_device=device, network_element=element,
            measurement_type_id=self.catalog["measurement_type"],
            measurement_unit_id=self.catalog["measurement_unit"],
        )
        for resource, record in (("measurements", measurement), ("network-elements", element)):
            with self.subTest(resource=resource):
                path = self.detail(resource, record.pk)
                before = type(record).objects.filter(pk=record.pk).values().get()
                self.assertEqual(self.client.get(path).status_code, 404)
                self.assertEqual(self.client.patch(path, {"name": "Blocked"}, format="json").status_code, 404)
                self.assertEqual(self.client.delete(path).status_code, 404)
                self.assertEqual(self.client.get(f"{API}{resource}/?department=3").json()["count"], 0)
                self.assertEqual(type(record).objects.filter(pk=record.pk).values().get(), before)
        self.client.force_authenticate(self.multi)
        for resource, record in (("measurements", measurement), ("network-elements", element)):
            self.assertEqual(self.client.get(self.detail(resource, record.pk)).status_code, 200)

    @override_settings(METADATA_ACCESS_POLICY="metadata.access.NoAccessPolicy")
    def test_default_policy_has_no_access(self):
        self.device()
        self.assertEqual(self.client.get(f"{API}physical-devices/").json()["count"], 0)
        self.assertEqual(self.client.get(f"{API}measurement-types/").json()["count"], 0)
        self.assertEqual(self.post("physical-devices", {"department": 2}).status_code, 403)
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get(f"{API}physical-devices/").status_code, (401, 403))

    def test_catalog_is_shared_and_only_manager_writes(self):
        rogue = PhysicalDeviceType.objects.create(department_id=3, name="Non-platform type")
        self.assertEqual(self.client.get(f"{API}physical-device-types/").json()["count"], 1)
        self.assertEqual(self.post("physical-device-types", {"name": "Pump"}).status_code, 403)
        response = self.post("physical-devices", {"department": 2, "name": "Invalid", "device_type": rogue.pk})
        self.assertEqual(response.status_code, 400)
        self.assertIn("device_type", response.data)

        self.client.force_authenticate(self.manager)
        response = self.post("physical-device-types", {"name": "Pump", "department": 3})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["department"], 1)
        pk = response.data["id"]
        path = self.detail("physical-device-types", pk)
        self.assertEqual(self.client.patch(path, {"description": "Demo catalog entry"}, format="json").status_code, 200)
        response = self.post("physical-device-types", {"name": "PUMP"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.delete(path).status_code, 204)
        response = self.post("physical-devices", {"department": 2, "name": "Archived type", "device_type": pk})
        self.assertEqual(response.status_code, 403)
        self.client.force_authenticate(self.editor)
        response = self.post("physical-devices", {"department": 2, "name": "Archived type", "device_type": pk})
        self.assertEqual(response.status_code, 400)
        self.assertIn("device_type", response.data)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.post("physical-device-types", {"name": "PUMP"}).status_code, 201)

    def test_database_rejects_cross_department_measurements(self):
        local_device, local_element = self.device(), self.element()
        other_device, other_element = self.device(department=3), self.element(department=3)
        for device, element in ((other_device, local_element), (local_device, other_element)):
            with self.subTest(device=device.pk, element=element.pk):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Measurement.objects.create(
                        department_id=2, name="Invalid", physical_device=device, network_element=element,
                        measurement_type_id=self.catalog["measurement_type"],
                        measurement_unit_id=self.catalog["measurement_unit"],
                    )

    def test_database_rejects_unsupported_network_geometry(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            NetworkElement.objects.create(
                department_id=2, name="Invalid", element_type_id=self.catalog["element_type"],
                geometry=MultiPoint(Point(33, 35), srid=4326),
            )

    def test_network_geometry_validation_and_bbox(self):
        for geometry in (POINT, LINE, POLYGON):
            response = self.post("network-elements", {
                "department": 2, "name": "GIS", "element_type": self.catalog["element_type"], "geometry": geometry,
            })
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.json()["geometry"], geometry)
        for invalid in (
            {"type": "MultiPoint", "coordinates": [[33, 35]]},
            {"type": "Point", "coordinates": [181, 35]},
            {"type": "Point", "coordinates": [33, True]},
            {"type": "Point", "coordinates": [33, 35, 0]},
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]},
            {**POINT, "crs": {"type": "name", "properties": {"name": "EPSG:3857"}}},
        ):
            with self.subTest(invalid=invalid):
                response = self.post("network-elements", {
                    "department": 2, "name": "Invalid", "element_type": self.catalog["element_type"],
                    "geometry": invalid,
                })
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("geometry", response.data)
        response = self.post("physical-devices", {
            "department": 2, "name": "Invalid", "device_type": self.catalog["device_type"], "location": LINE,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(f"{API}network-elements/?bbox=33,35,34,36").json()["count"], 3)
        self.assertEqual(self.client.get(f"{API}network-elements/?bbox=0,0,1,1").json()["count"], 0)
        self.assertEqual(self.client.get(f"{API}network-elements/?bbox=34,35,33,36").status_code, 400)

    def test_external_identifier_updates_preserve_history(self):
        element = self.element()
        path = self.detail("network-elements", element.pk)
        initial = [{"source": "KIOS", "value": "same"}, {"source": "ERP", "value": "retired"}]
        response = self.client.patch(path, {"external_identifiers": initial}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        keep_id, retired_id = [item["id"] for item in response.data["external_identifiers"]]
        response = self.client.patch(path, {"external_identifiers": [initial[0], initial[0]]}, format="json")
        self.assertEqual(response.status_code, 400)

        response = self.client.patch(path, {"external_identifiers": initial[:1]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in response.data["external_identifiers"]], [keep_id])
        self.assertEqual(self.client.get(path).json()["external_identifiers"], response.data["external_identifiers"])
        self.assertEqual(ExternalIdentifier.objects.get(pk=retired_id).deleted_by_id, self.editor.pk)
        self.assertEqual(self.client.get(f"{API}network-elements/?identifier=retired").json()["count"], 0)
        self.assertEqual(self.client.get(f"{API}network-elements/?identifier=same").json()["count"], 1)

    def test_patch_rejects_incomplete_identifiers_without_changing_stored_data(self):
        element = self.element()
        ExternalIdentifier.objects.create(network_element=element, source="ERP", value="existing-101")
        path = self.detail("network-elements", element.pk)
        before_element = NetworkElement.objects.filter(pk=element.pk).values().get()
        before_identifiers = list(ExternalIdentifier.objects.filter(network_element=element).values())
        cases = (
            ([{"value": "new-101"}], 0, {"source"}),
            ([{"source": "ERP"}], 0, {"value"}),
            ([{}], 0, {"source", "value"}),
            ([{"source": "SCADA", "value": "valid-101"}, {"source": "ERP"}], 1, {"value"}),
        )
        self.client.raise_request_exception = False
        for identifiers, index, missing_fields in cases:
            with self.subTest(identifiers=identifiers):
                response = self.client.patch(path, {
                    "name": "Must not be saved", "external_identifiers": identifiers,
                }, format="json")
                self.assertEqual(response.status_code, 400, response.content)
                errors = response.data["external_identifiers"][index]
                self.assertEqual(set(errors), missing_fields)
                for field in missing_fields:
                    self.assertEqual(str(errors[field][0]), "This field is required.")
                    self.assertEqual(errors[field][0].code, "required")
                self.assertEqual(NetworkElement.objects.filter(pk=element.pk).values().get(), before_element)
                self.assertEqual(
                    list(ExternalIdentifier.objects.filter(network_element=element).values()), before_identifiers,
                )

    def test_patch_can_omit_or_clear_external_identifiers(self):
        element = self.element()
        identifier = ExternalIdentifier.objects.create(network_element=element, source="ERP", value="existing-101")
        path = self.detail("network-elements", element.pk)
        before = ExternalIdentifier.objects.filter(pk=identifier.pk).values().get()
        response = self.client.patch(path, {"name": "Renamed site"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["name"], "Renamed site")
        self.assertEqual(response.data["external_identifiers"], [
            {"id": identifier.pk, "source": "ERP", "value": "existing-101"},
        ])
        self.assertEqual(ExternalIdentifier.objects.filter(pk=identifier.pk).values().get(), before)
        response = self.client.patch(path, {"external_identifiers": []}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["external_identifiers"], [])
        identifier.refresh_from_db()
        self.assertIsNotNone(identifier.deleted_at)
        self.assertEqual(identifier.deleted_by_id, self.editor.pk)
        self.assertEqual(ExternalIdentifier.objects.filter(network_element=element).count(), 1)

    def test_search_sorting_filters_and_pagination(self):
        first = self.device(name="Matching station")
        second = self.device(name="Matching station")
        self.device(name="Other")
        self.device(department=3, name="Matching station")
        url = f"{API}physical-devices/?search=Matching&ordering=name&page_size=1"
        page = self.client.get(url).json()
        self.assertEqual(page["count"], 2)
        self.assertEqual(page["results"][0]["id"], first.pk)
        self.assertEqual(self.client.get(f"{url}&page=2").json()["results"][0]["id"], second.pk)
        self.assertEqual(self.client.get(f"{API}physical-devices/?device_type=0").status_code, 400)
        self.assertEqual(self.client.get(f"{API}physical-devices/?device_type=999").json()["count"], 0)

    def test_identifiers_are_unique_per_external_system_across_elements(self):
        first = self.post("network-elements", {
            "department": 2, "name": "First", "element_type": self.catalog["element_type"],
            "external_identifiers": [{"source": "ERP", "value": "asset-101"}],
        })
        self.assertEqual(first.status_code, 201, first.data)
        self.client.force_authenticate(self.multi)
        duplicate = self.post("network-elements", {
            "department": 3, "name": "Duplicate", "element_type": self.catalog["element_type"],
            "external_identifiers": [{"source": "ERP", "value": "asset-101"}],
        })
        self.assertEqual(duplicate.status_code, 400, duplicate.data)
        self.assertIn("external_identifiers", duplicate.data)
        self.assertFalse(NetworkElement.objects.filter(name="Duplicate").exists())
        distinct_system = self.post("network-elements", {
            "department": 3, "name": "Different system", "element_type": self.catalog["element_type"],
            "external_identifiers": [{"source": "SCADA", "value": "asset-101"}],
        })
        self.assertEqual(distinct_system.status_code, 201, distinct_system.data)

    def test_database_rejects_duplicate_active_external_identifiers(self):
        first, second = self.element(name="First"), self.element(name="Second")
        ExternalIdentifier.objects.create(network_element=first, source="ERP", value="asset-101")
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExternalIdentifier.objects.create(network_element=second, source="ERP", value="asset-101")

    def test_archived_identifiers_remain_stored_and_can_be_reused(self):
        first = self.element(name="Old")
        identifier = ExternalIdentifier.objects.create(network_element=first, source="ERP", value="asset-101")
        self.assertEqual(self.client.delete(self.detail("network-elements", first.pk)).status_code, 204)
        replacement = self.post("network-elements", {
            "department": 2, "name": "Replacement", "element_type": self.catalog["element_type"],
            "external_identifiers": [{"source": "ERP", "value": "asset-101"}],
        })
        self.assertEqual(replacement.status_code, 201, replacement.data)
        identifier.refresh_from_db()
        self.assertIsNotNone(identifier.deleted_at)
        self.assertEqual(identifier.network_element_id, first.pk)
        self.assertNotEqual(replacement.data["external_identifiers"][0]["id"], identifier.pk)

    def test_identifier_search_uses_active_values_and_keeps_department_scope(self):
        first = self.element(name="Visible station")
        second = self.element(name="Other station")
        hidden = self.element(department=3, name="Hidden station")
        for element, source, value in (
            (first, "ERP", "ACTIVE-101"), (first, "SCADA", "ACTIVE-102"),
            (second, "GIS", "ACTIVE-103"), (hidden, "ERP", "ACTIVE-HIDDEN"),
        ):
            ExternalIdentifier.objects.create(network_element=element, source=source, value=value)
        retired = ExternalIdentifier.objects.create(network_element=first, source="OLD", value="RETIRED-101")
        ExternalIdentifier.objects.filter(pk=retired.pk).archive(self.editor)
        self.assertEqual(self.client.get(f"{API}network-elements/?search=RETIRED-101").json()["count"], 0)
        combined = self.client.get(f"{API}network-elements/?search=Visible%20ACTIVE-101").json()
        self.assertEqual([row["id"] for row in combined["results"]], [first.pk])
        self.assertEqual(self.client.get(f"{API}network-elements/?search=ERP").json()["count"], 1)
        page = self.client.get(f"{API}network-elements/?search=ACTIVE&ordering=id&page_size=1").json()
        self.assertEqual(page["count"], 2)
        self.assertEqual(page["results"][0]["id"], first.pk)
        self.assertEqual(self.client.get(page["next"]).json()["results"][0]["id"], second.pk)

    def test_import_links_all_sheets_and_api_can_read_result(self):
        response = self.upload(self.workbook_sheets())
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["created"], {"Physical Devices": 1, "Network Elements": 1, "Measurements": 1})
        measurement = Measurement.objects.get()
        self.assertEqual(measurement.physical_device.name, "Imported device")
        self.assertEqual(measurement.network_element.external_identifiers.get().value, "SITE-101")
        result = self.client.get(f"{API}measurements/?search=Imported").json()["results"][0]
        self.assertEqual(result["physical_device"], measurement.physical_device_id)
        self.assertEqual(result["network_element"], measurement.network_element_id)

    def test_generated_example_workbook_imports_all_three_domains(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "example.xlsx"
            call_command("metadata_workbook", str(path), example=True, stdout=StringIO())
            response = self.client.post(
                f"{API}imports/excel/",
                {"department": 2, "file": SimpleUploadedFile(path.name, path.read_bytes())},
                format="multipart",
            )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["created"], {"Physical Devices": 1, "Network Elements": 1, "Measurements": 1})
        measurement = Measurement.objects.get()
        self.assertEqual(measurement.physical_device.name, "Example station")
        self.assertEqual(measurement.network_element.external_identifiers.get().value, "SITE-101")

    def test_import_invalid_late_row_rolls_back_all_changes(self):
        sheets = self.workbook_sheets()
        sheets["Measurements"].append(("Invalid", "@station", "@site", 999, self.catalog["measurement_unit"]))
        response = self.upload(sheets)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.json()["errors"][0]["sheet"], "Measurements")
        self.assertEqual(response.json()["errors"][0]["row"], 3)
        self.assertIn("measurement_type", response.json()["errors"][0]["errors"])
        for model in (PhysicalDevice, NetworkElement, ExternalIdentifier, Measurement):
            self.assertFalse(model.objects.exists())

    def test_import_duplicate_identifiers_reports_row_and_rolls_back(self):
        sheets = self.workbook_sheets()
        sheets["Network Elements"].append((
            "duplicate", "Duplicate site", self.catalog["element_type"],
            '[{"source":"KIOS","value":"SITE-101"}]',
        ))
        response = self.upload(sheets)
        self.assertEqual(response.status_code, 400, response.data)
        error = response.data["errors"][0]
        self.assertEqual((error["sheet"], error["row"]), ("Network Elements", 3))
        self.assertIn("external_identifiers", error["errors"])
        for model in (PhysicalDevice, NetworkElement, ExternalIdentifier, Measurement):
            self.assertFalse(model.objects.exists())

    def test_import_rejects_wrong_headers_formulas_and_corrupt_data(self):
        samples = (
            ({"Physical Devices": [("name",), ("Missing type",)]}, "header", 1),
            ({"Physical Devices": [("name", "device_type"), ("=1+2", self.catalog["device_type"])]}, "name", 2),
            ({"Physical Devices": [
                ("ref", "name", "device_type"), ("same", "First", self.catalog["device_type"]),
                ("same", "Second", self.catalog["device_type"]),
            ]}, "ref", 3),
        )
        for sheets, field, row in samples:
            response = self.upload(sheets)
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(response.json()["errors"][0]["row"], row)
            self.assertIn(field, response.json()["errors"][0]["errors"])
        response = self.client.post(
            f"{API}imports/excel/", {"department": 2, "file": SimpleUploadedFile("bad.xlsx", b"not an xlsx")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.json()["errors"][0]["errors"])
        self.assertFalse(PhysicalDevice.objects.exists())

    def test_import_accepts_existing_ids_and_blocks_other_departments(self):
        device, element = self.device(), self.element()
        sheets = {"Measurements": [
            ("name", "physical_device", "network_element", "measurement_type", "measurement_unit"),
            ("Existing parents", device.pk, element.pk, self.catalog["measurement_type"], self.catalog["measurement_unit"]),
        ]}
        self.assertEqual(self.upload(sheets, department=3).status_code, 403)
        self.client.force_authenticate(self.multi)
        response = self.upload(sheets, department=3)
        self.assertEqual(response.status_code, 400)
        self.assertIn("physical_device", response.json()["errors"][0]["errors"])
        self.assertFalse(Measurement.objects.exists())
        self.assertEqual(self.upload(sheets).status_code, 201)

    def test_collection_config_validates_jsonb_values(self):
        data = self.measurement_data(self.device(), self.element())
        for invalid in (["not an object"], {"nested": ["embedded\x00null"]}):
            response = self.post("measurements", {**data, "data_collection_config": invalid})
            self.assertEqual(response.status_code, 400)
            self.assertIn("data_collection_config", response.data)
        self.assertFalse(Measurement.objects.exists())

    def test_optional_accounts_collection_settings_and_audit(self):
        data = self.measurement_data(self.device(), self.element())
        data.update({
            "customer_account": "CUSTOMER-101", "meter_account": "METER-202",
            "data_collection_config": {
                "protocol": "https", "endpoint": "https://example.invalid/metadata",
                "source_identifier": "SOURCE-1", "extra_settings": {"interval_seconds": 60},
            },
        })
        response = self.post("measurements", data)
        self.assertEqual(response.status_code, 201, response.data)
        for field in ("customer_account", "meter_account", "data_collection_config"):
            self.assertEqual(response.data[field], data[field])
        self.assertEqual(response.data["created_by"], self.editor.pk)
        self.assertEqual(response.data["updated_by"], self.editor.pk)
        self.assertTrue(response.data["is_active"])
        self.assertEqual(self.client.get(f"{API}measurements/?search=METER-202").json()["count"], 1)
        self.client.force_authenticate(self.multi)
        response = self.client.patch(
            self.detail("measurements", response.data["id"]), {"name": "Revised"}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["created_by"], self.editor.pk)
        self.assertEqual(response.data["updated_by"], self.multi.pk)

    def test_network_model_identifiers_are_persisted_and_searchable(self):
        response = self.post("network-elements", {
            "department": 2, "name": "Site", "element_type": self.catalog["element_type"],
            "dma_model_id": "DMA-101", "strategic_model_id": "STRATEGIC-202",
        })
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["dma_model_id"], "DMA-101")
        self.assertEqual(response.data["strategic_model_id"], "STRATEGIC-202")
        self.assertEqual(self.client.get(f"{API}network-elements/?search=STRATEGIC-202").json()["count"], 1)

    def test_historical_list_values_are_readable_but_cannot_be_selected(self):
        unused = MeasurementUnit.objects.create(department_id=1, name="Archived unit")
        self.client.force_authenticate(self.manager)
        path = self.detail("measurement-units", unused.pk)
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.get(path).status_code, 404)
        response = self.client.get(f"{path}?include_inactive=true")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["is_active"])
        data = self.measurement_data(self.device(), self.element())
        data["measurement_unit"] = unused.pk
        self.assertEqual(self.post("measurements", data).status_code, 400)

    def test_partial_update_revalidates_unchanged_references(self):
        data = self.measurement_data(self.device(), self.element())
        response = self.post("measurements", data)
        MeasurementType.objects.filter(pk=self.catalog["measurement_type"]).archive(self.editor)
        response = self.client.patch(
            self.detail("measurements", response.data["id"]), {"description": "Edited"}, format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("measurement_type", response.data)

    def test_collection_settings_validate_named_fields(self):
        data = self.measurement_data(self.device(), self.element())
        for invalid in ({"extra_settings": []}, {"protocol": "x" * 51}, {"endpoint": True}):
            response = self.post("measurements", {**data, "data_collection_config": invalid})
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn("data_collection_config", response.data)

    def test_excel_import_persists_account_and_model_identifiers(self):
        sheets = self.workbook_sheets()
        sheets["Measurements"][0] += ("customer_account", "meter_account", "data_collection_config")
        sheets["Measurements"][1] += (
            "CUSTOMER-X", "METER-Y", '{"protocol":"mqtt","source_identifier":"test","extra_settings":{}}',
        )
        sheets["Network Elements"][0] += ("dma_model_id", "strategic_model_id")
        sheets["Network Elements"][1] += ("DMA-X", "STRATEGIC-Y")
        response = self.upload(sheets)
        self.assertEqual(response.status_code, 201, response.data)
        measurement = Measurement.objects.get()
        self.assertEqual(measurement.customer_account, "CUSTOMER-X")
        self.assertEqual(measurement.meter_account, "METER-Y")
        self.assertEqual(measurement.data_collection_config["protocol"], "mqtt")
        self.assertEqual(measurement.network_element.dma_model_id, "DMA-X")
        self.assertEqual(measurement.created_by_id, self.editor.pk)


@override_settings(METADATA_ACCESS_POLICY=POLICY, METADATA_PLATFORM_DEPARTMENT_ID=1)
class MetadataConcurrencyTests(APITransactionTestCase):
    def setUp(self):
        catalog = create_catalog()
        self.editor = get_user_model().objects.create_user(username="editor")
        self.device = PhysicalDevice.objects.create(
            department_id=2, name="Station", device_type_id=catalog["device_type"]
        )
        element = NetworkElement.objects.create(department_id=2, name="Site", element_type_id=catalog["element_type"])
        self.measurement_type = catalog["measurement_type"]
        self.payload = {
            "department": 2, "name": "Temperature", "physical_device": self.device.pk,
            "network_element": element.pk, "measurement_type": self.measurement_type,
            "measurement_unit": catalog["measurement_unit"],
        }

    def assert_archive_serializes_measurement(self, url, archive_user, invalid_field):
        self.client.force_authenticate(archive_user)
        pid_queue = Queue()

        def post_measurement():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pid_queue.put(cursor.fetchone()[0])
                client = APIClient()
                client.force_authenticate(self.editor)
                return client.post(f"{API}measurements/", self.payload, format="json")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as worker:
            with transaction.atomic():
                result = self.client.delete(url)
                self.assertEqual(result.status_code, 204)
                pending = worker.submit(post_measurement)
                pid = pid_queue.get(timeout=5)
                deadline = monotonic() + 5
                while monotonic() < deadline and not pending.done():
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1 FROM pg_locks WHERE pid = %s AND NOT granted", [pid])
                        if cursor.fetchone():
                            break
                    sleep(0.02)
                else:
                    self.fail("The measurement request did not wait on the archive transaction.")

            result = pending.result(timeout=5)
            self.assertEqual(result.status_code, 400, result.data)
            self.assertIn(invalid_field, result.data)
        self.assertFalse(Measurement.objects.exists())

    def test_measurement_waits_for_concurrent_device_archive(self):
        self.assert_archive_serializes_measurement(
            f"{API}physical-devices/{self.device.pk}/", self.editor, "physical_device"
        )

    def test_measurement_waits_for_concurrent_catalog_archive(self):
        manager = get_user_model().objects.create_user(username="catalog-manager")
        self.assert_archive_serializes_measurement(
            f"{API}measurement-types/{self.measurement_type}/", manager, "measurement_type"
        )

    def assert_identifier_race_rejected(self, *, importing):
        self.client.force_authenticate(self.editor)
        element_type = NetworkElementType.objects.get().pk
        pair = {"source": "ERP", "value": "concurrent-101"}
        pid_queue = Queue()
        writer = get_user_model().objects.create_user(username="multi")

        def create_competing_element():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pid_queue.put(cursor.fetchone()[0])
                client = APIClient()
                client.force_authenticate(writer)
                if importing:
                    workbook = make_workbook({"Network Elements": [
                        ("name", "element_type", "external_identifiers"),
                        ("Concurrent", element_type, '[{"source":"ERP","value":"concurrent-101"}]'),
                    ]})
                    return client.post(
                        f"{API}imports/excel/", {"department": 3, "file": workbook}, format="multipart",
                    )
                return client.post(f"{API}network-elements/", {
                    "department": 3, "name": "Concurrent", "element_type": element_type,
                    "external_identifiers": [pair],
                }, format="json")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as worker:
            with transaction.atomic():
                response = self.client.post(f"{API}network-elements/", {
                    "department": 2, "name": "Original", "element_type": element_type,
                    "external_identifiers": [pair],
                }, format="json")
                self.assertEqual(response.status_code, 201, response.data)
                pending = worker.submit(create_competing_element)
                pid = pid_queue.get(timeout=5)
                deadline = monotonic() + 5
                while monotonic() < deadline and not pending.done():
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1 FROM pg_locks WHERE pid = %s AND NOT granted", [pid])
                        if cursor.fetchone():
                            break
                    sleep(0.02)
                else:
                    self.fail("The duplicate identifier did not wait for the competing transaction.")
            response = pending.result(timeout=5)
        self.assertEqual(response.status_code, 400, response.data)
        if importing:
            error = response.data["errors"][0]
            self.assertEqual((error["sheet"], error["row"]), ("Network Elements", 2))
            self.assertIn("external_identifiers", error["errors"])
        else:
            self.assertIn("external_identifiers", response.data)
        self.assertFalse(NetworkElement.objects.filter(name="Concurrent").exists())
        self.assertEqual(ExternalIdentifier.objects.active().filter(**pair).count(), 1)

    def test_concurrent_identifier_claim_returns_api_field_error(self):
        self.assert_identifier_race_rejected(importing=False)

    def test_concurrent_identifier_claim_returns_excel_row_error(self):
        self.assert_identifier_race_rejected(importing=True)
