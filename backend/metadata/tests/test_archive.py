from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from api_keys.models import APIKey
from local_departments.models import Department
from platform_security.models import UserDepartment, UserRole

from ..models import ExternalIdentifier, Measurement, NetworkElement, PhysicalDevice, PhysicalDeviceType
from .test_backend import API, create_catalog

POLICY = "platform_security.access.DepartmentAccessPolicy"


@override_settings(METADATA_ACCESS_POLICY=POLICY, METADATA_PLATFORM_DEPARTMENT_ID=1)
class ArchivedRecordTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catalog = create_catalog()
        cls.users = {}
        for name, role, departments in (
            ("viewer", "VIEWER", (2,)), ("editor", "EDITOR", (2,)), ("dept-admin", "DEPARTMENT_ADMIN", (2,)),
            ("south-admin", "DEPARTMENT_ADMIN", (3,)), ("system-admin", "SYSTEM_ADMIN", ()),
        ):
            user = get_user_model().objects.create_user(username=name)
            UserRole.objects.create(user=user, role=role)
            for department in departments:
                UserDepartment.objects.create(user=user, department_id=department)
            cls.users[name] = user

    def as_user(self, name):
        self.client.force_authenticate(self.users[name])

    def make_records(self):
        self.as_user("editor")
        device = self.client.post(f"{API}physical-devices/", {
            "department": 2, "name": "RTU 1", "device_type": self.catalog["device_type"],
            "location": {"type": "Point", "coordinates": [33.38, 35.17]},
        }, format="json").json()
        element = self.client.post(f"{API}network-elements/", {
            "department": 2, "name": "Inlet 1", "element_type": self.catalog["element_type"],
            "external_identifiers": [{"source": "ERP", "value": "NE-1"}],
        }, format="json").json()
        measurement = self.client.post(f"{API}measurements/", {
            "department": 2, "name": "Flow 1", "physical_device": device["id"], "network_element": element["id"],
            "measurement_type": self.catalog["measurement_type"], "measurement_unit": self.catalog["measurement_unit"],
            "data_collection_config": {"protocol": "MQTT"},
        }, format="json").json()
        return device["id"], element["id"], measurement["id"]

    def archive(self, resource, pk):
        self.as_user("editor")
        self.assertEqual(self.client.delete(f"{API}{resource}/{pk}/").status_code, 204)

    def listed(self, user, resource, department=2):
        self.as_user(user)
        response = self.client.get(f"{API}{resource}/", {"department": department, "include_archived": "true"})
        self.assertEqual(response.status_code, 200)
        return {row["id"]: row["is_active"] for row in response.json()["results"]}

    def test_only_department_and_system_admins_see_archived_records(self):
        _, _, measurement = self.make_records()
        self.archive("measurements", measurement)
        for user in ("dept-admin", "system-admin"):
            self.assertEqual(self.listed(user, "measurements"), {measurement: False}, user)
        for user in ("viewer", "editor"):
            self.assertEqual(self.listed(user, "measurements"), {}, user)
        # Without the parameter nobody sees them, and other Departments' admins never do.
        self.as_user("dept-admin")
        self.assertEqual(self.client.get(f"{API}measurements/", {"department": 2}).json()["count"], 0)
        self.assertEqual(self.listed("south-admin", "measurements", department=3), {})

    def test_restore_brings_a_record_back_for_admins_only(self):
        device, _, measurement = self.make_records()
        self.archive("measurements", measurement)
        for user in ("viewer", "editor", "south-admin"):
            self.as_user(user)
            self.assertEqual(self.client.post(f"{API}measurements/{measurement}/restore/").status_code, 404, user)
        self.as_user("dept-admin")
        response = self.client.post(f"{API}measurements/{measurement}/restore/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["is_active"])
        self.assertEqual(Measurement.objects.get(pk=measurement).data_collection_config, {"protocol": "MQTT"})
        # An active record cannot be "restored".
        self.assertEqual(self.client.post(f"{API}physical-devices/{device}/restore/").status_code, 404)

    def test_restore_requires_the_records_it_uses_to_be_active(self):
        device, _, measurement = self.make_records()
        self.archive("measurements", measurement)
        self.archive("physical-devices", device)
        self.as_user("system-admin")
        blocked = self.client.post(f"{API}measurements/{measurement}/restore/")
        self.assertEqual(blocked.status_code, 409)
        self.assertIn("Restore the physical device 'RTU 1' first", blocked.json()["detail"])
        self.assertEqual(self.client.post(f"{API}physical-devices/{device}/restore/").status_code, 200)
        self.assertEqual(self.client.post(f"{API}measurements/{measurement}/restore/").status_code, 200)

    def test_restoring_an_element_restores_its_identifiers_unless_taken(self):
        _, element, measurement = self.make_records()
        self.archive("measurements", measurement)
        self.archive("network-elements", element)
        self.assertFalse(ExternalIdentifier.objects.active().filter(value="NE-1").exists())
        self.as_user("editor")
        clash = self.client.post(f"{API}network-elements/", {
            "department": 2, "name": "Inlet 1 (new)", "element_type": self.catalog["element_type"],
            "external_identifiers": [{"source": "ERP", "value": "NE-1"}],
        }, format="json").json()
        self.as_user("dept-admin")
        conflict = self.client.post(f"{API}network-elements/{element}/restore/")
        self.assertEqual(conflict.status_code, 409)
        self.assertFalse(NetworkElement.objects.get(pk=element).deleted_at is None)  # nothing half-restored
        self.archive("network-elements", clash["id"])
        self.as_user("dept-admin")
        restored = self.client.post(f"{API}network-elements/{element}/restore/")
        self.assertEqual(restored.status_code, 200, restored.content)
        self.assertEqual([i["value"] for i in restored.json()["external_identifiers"]], ["NE-1"])

    def test_permanent_delete_removes_archived_records_in_order(self):
        device, element, measurement = self.make_records()
        self.archive("measurements", measurement)
        self.archive("physical-devices", device)
        self.archive("network-elements", element)
        for user in ("viewer", "editor", "south-admin"):
            self.as_user(user)
            self.assertEqual(self.client.delete(f"{API}measurements/{measurement}/purge/").status_code, 404, user)
        self.as_user("dept-admin")
        used = self.client.delete(f"{API}physical-devices/{device}/purge/")
        self.assertEqual(used.status_code, 409)
        self.assertEqual(self.client.delete(f"{API}measurements/{measurement}/purge/").status_code, 204)
        self.assertEqual(self.client.delete(f"{API}physical-devices/{device}/purge/").status_code, 204)
        self.assertEqual(self.client.delete(f"{API}network-elements/{element}/purge/").status_code, 204)
        self.assertFalse(Measurement.objects.filter(pk=measurement).exists())
        self.assertFalse(PhysicalDevice.objects.filter(pk=device).exists())
        self.assertFalse(NetworkElement.objects.filter(pk=element).exists())
        self.assertFalse(ExternalIdentifier.objects.filter(value="NE-1").exists())

    def test_active_records_cannot_be_permanently_deleted(self):
        device, _, _ = self.make_records()
        self.as_user("system-admin")
        self.assertEqual(self.client.delete(f"{API}physical-devices/{device}/purge/").status_code, 404)
        self.assertTrue(PhysicalDevice.objects.filter(pk=device).exists())

    def test_department_and_system_admins_delete_shared_list_entries(self):
        for admin in ("dept-admin", "system-admin"):
            entry = PhysicalDeviceType.objects.create(department_id=1, name=f"Old logger {admin}")
            self.as_user(admin)
            self.assertEqual(self.client.delete(f"{API}physical-device-types/{entry.pk}/").status_code, 204, admin)
            listed = self.client.get(f"{API}physical-device-types/", {"include_archived": "true", "page_size": 100}).json()
            self.assertIn(entry.pk, [row["id"] for row in listed["results"] if row["is_active"] is False], admin)
            self.assertEqual(self.client.post(f"{API}physical-device-types/{entry.pk}/restore/").status_code, 200, admin)
            self.assertEqual(self.client.delete(f"{API}physical-device-types/{entry.pk}/").status_code, 204, admin)
            self.assertEqual(self.client.delete(f"{API}physical-device-types/{entry.pk}/purge/").status_code, 204, admin)
            self.assertFalse(PhysicalDeviceType.objects.filter(pk=entry.pk).exists(), admin)

    def test_department_and_system_admins_add_and_edit_shared_list_entries(self):
        for admin in ("dept-admin", "system-admin"):
            self.as_user(admin)
            created = self.client.post(f"{API}physical-device-types/", {"department": 1, "name": f"New {admin}"}, format="json")
            self.assertEqual(created.status_code, 201, admin)
            edited = self.client.patch(f"{API}physical-device-types/{created.json()['id']}/", {"description": "x"}, format="json")
            self.assertEqual(edited.status_code, 200, admin)
        for user in ("viewer", "editor"):
            self.as_user(user)
            self.assertEqual(self.client.post(f"{API}physical-device-types/", {"department": 1, "name": f"New {user}"}, format="json").status_code, 403, user)

    def test_viewers_and_editors_cannot_change_shared_list_entries(self):
        entry = PhysicalDeviceType.objects.create(department_id=1, name="Logger")
        for user in ("viewer", "editor"):
            self.as_user(user)
            self.assertEqual(self.client.delete(f"{API}physical-device-types/{entry.pk}/").status_code, 403, user)
            listed = self.client.get(f"{API}physical-device-types/", {"include_archived": "true", "page_size": 100}).json()
            self.assertTrue(all(row["is_active"] for row in listed["results"]), user)
        self.assertIsNone(PhysicalDeviceType.objects.get(pk=entry.pk).deleted_at)

    def test_shared_list_entry_in_use_is_protected(self):
        self.make_records()
        self.as_user("dept-admin")
        used = self.client.delete(f"{API}physical-device-types/{self.catalog['device_type']}/")
        self.assertEqual(used.status_code, 409)
        self.as_user("system-admin")
        PhysicalDeviceType.objects.create(department_id=1, name="Clash")
        clash = PhysicalDeviceType.objects.create(department_id=1, name="clash", deleted_at=timezone.now())
        self.assertEqual(self.client.post(f"{API}physical-device-types/{clash.pk}/restore/").status_code, 409)

    def test_api_keys_cannot_see_or_change_archived_records(self):
        _, _, measurement = self.make_records()
        self.archive("measurements", measurement)
        key, raw = APIKey.issue(name="reader", department=Department.objects.get(pk=2), creator=self.users["system-admin"],
                                expires_at=timezone.now() + timedelta(days=1))
        self.client.force_authenticate(None)
        listed = self.client.get(f"{API}measurements/", {"department": 2, "include_archived": "true"}, HTTP_X_API_KEY=raw)
        self.assertEqual(listed.json()["count"], 0)
        self.assertIn(self.client.post(f"{API}measurements/{measurement}/restore/", HTTP_X_API_KEY=raw).status_code,
                      (401, 403, 404))
