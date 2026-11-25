from io import BytesIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from ..exports import DEVICE_COLUMNS, ELEMENT_COLUMNS, MEASUREMENT_COLUMNS
from ..models import Measurement, NetworkElement, PhysicalDevice
from .test_backend import API, FixturePolicy, create_catalog

CLIENT_SAMPLE = Path(__file__).resolve().parents[3] / "docs" / "testing" / "limassol-real-data.xlsx"


def relabel(content, department):
    """The exported workbook with every Department cell set to ``department``."""
    workbook = load_workbook(BytesIO(content))
    for sheet in workbook.worksheets:
        for (cell,) in sheet.iter_rows(min_row=2, max_col=1):
            cell.value = department
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


class ExportPolicy(FixturePolicy):
    def can_manage_controlled_lists(self, request):
        return request.user.get_username() == "multi"


@override_settings(METADATA_ACCESS_POLICY="metadata.tests.test_export.ExportPolicy", METADATA_PLATFORM_DEPARTMENT_ID=1)
class ClientLayoutExportTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        create_catalog()
        users = get_user_model().objects
        cls.multi = users.create_user(username="multi")
        cls.viewer = users.create_user(username="viewer")

    def setUp(self):
        self.client.force_authenticate(self.multi)

    def upload(self, content, department):
        upload = SimpleUploadedFile("metadata.xlsx", content)
        return self.client.post(f"{API}imports/excel/", {"file": upload, "department": department}, format="multipart")

    def export(self, department):
        return self.client.get(f"{API}exports/excel/", {"department": department})

    @staticmethod
    def snapshot(department):
        devices = {d.name: (d.device_type.name, d.location and d.location.coords, d.communication_parameters)
                   for d in PhysicalDevice.objects.active().filter(department_id=department)}
        elements = {
            e.name: (e.element_type.name, e.geometry and e.geometry.coords, e.elevation, e.network_area, e.address,
                     e.dma_model_id, e.strategic_model_id, sorted(i.value for i in e.active_external_identifiers))
            for e in NetworkElement.objects.active().filter(department_id=department)
        }
        measurements = {
            m.name: (m.measurement_type.name, m.measurement_unit.name, m.description, m.physical_device.name,
                     m.network_element.name, m.customer_account, m.meter_account, m.data_collection_config)
            for m in Measurement.objects.active().filter(department_id=department)
        }
        return devices, elements, measurements

    def test_export_uses_client_layout_and_imports_again_unchanged(self):
        imported = self.upload(CLIENT_SAMPLE.read_bytes(), 2)
        self.assertEqual(imported.status_code, 201, imported.data)

        response = self.export(2)
        self.assertEqual(response.status_code, 200)
        self.assertIn('filename="Sensor_Metadata_North.xlsx"', response["Content-Disposition"])
        workbook = load_workbook(BytesIO(response.content))
        self.assertEqual(workbook.sheetnames, ["Measurements", "NetworkElements", "Physical_devices"])
        for title, columns, rows in (("Measurements", MEASUREMENT_COLUMNS, 8),
                                     ("NetworkElements", ELEMENT_COLUMNS, 4),
                                     ("Physical_devices", DEVICE_COLUMNS, 4)):
            sheet = list(workbook[title].iter_rows(values_only=True))
            self.assertEqual(sheet[0], columns)
            self.assertEqual(len(sheet) - 1, rows)
        first = dict(zip(MEASUREMENT_COLUMNS, next(workbook["Measurements"].iter_rows(min_row=2, values_only=True))))
        self.assertEqual(first["MeasurementId"], "LIM-M001")
        self.assertEqual(first["NetworkElementId"], "LIM-NE01")
        self.assertEqual(first["PhysicalDeviceId"], "LIM-DV01")
        self.assertEqual(first["SensorStationName"], "Logger Limassol Centre")
        workbook.close()

        again = self.upload(relabel(response.content, "South"), 3)
        self.assertEqual(again.status_code, 201, again.data)
        # The shared list entries created by the first import are reused.
        self.assertEqual(again.data["created"], {**imported.data["created"], "New shared list entries": 0})
        self.assertEqual(self.snapshot(3), self.snapshot(2))

    def test_export_requires_read_access(self):
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.export(3).status_code, 403)
        self.assertEqual(self.export(2).status_code, 200)
        self.assertEqual(self.client.get(f"{API}exports/excel/").status_code, 400)


@override_settings(METADATA_ACCESS_POLICY="metadata.tests.test_export.ExportPolicy", METADATA_PLATFORM_DEPARTMENT_ID=1)
class ClientDepartmentColumnTests(ClientLayoutExportTests):
    test_export_uses_client_layout_and_imports_again_unchanged = None
    test_export_requires_read_access = None

    def test_rows_for_another_department_are_rejected_and_nothing_is_saved(self):
        self.upload(CLIENT_SAMPLE.read_bytes(), 2)
        exported = self.export(2).content  # Department column says "North"
        response = self.upload(exported, 3)  # 3 is "South"
        self.assertEqual(response.status_code, 400)
        errors = response.data["errors"]
        self.assertEqual({e["sheet"] for e in errors}, {"Measurements", "NetworkElements", "Physical_devices"})
        self.assertIn("belongs to Department 'North'", errors[0]["errors"]["Department"][0])
        self.assertIn("importing into 'South'", errors[0]["errors"]["Department"][0])
        self.assertFalse(PhysicalDevice.objects.filter(department_id=3).exists())

    def test_unknown_department_labels_stay_informational(self):
        # The sample workbook says "Limassol", which is not a Department here.
        self.assertEqual(self.upload(CLIENT_SAMPLE.read_bytes(), 3).status_code, 201)


@override_settings(METADATA_ACCESS_POLICY="metadata.tests.test_export.ExportPolicy", METADATA_PLATFORM_DEPARTMENT_ID=1)
class ImportTemplateTests(APITestCase):
    def test_signed_in_users_download_the_import_template(self):
        from ..imports import SHEETS

        self.client.force_authenticate(get_user_model().objects.create_user(username="anyone"))
        response = self.client.get(f"{API}imports/excel/template/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('filename="metadata-import-template.xlsx"', response["Content-Disposition"])
        workbook = load_workbook(BytesIO(response.content))
        self.assertEqual(workbook.sheetnames, list(SHEETS))
        for name, spec in SHEETS.items():
            rows = list(workbook[name].iter_rows(values_only=True))
            self.assertEqual(rows, [(*spec.required, *spec.optional)])
            self.assertTrue(all(cell.font.b for cell in workbook[name][1][:len(spec.required)]))

    def test_template_requires_sign_in(self):
        self.assertIn(self.client.get(f"{API}imports/excel/template/").status_code, (401, 403))
