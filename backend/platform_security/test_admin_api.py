"""Phase 2 API surface: users, departments, /devices, configuration, OpenAPI."""

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from rest_framework.test import APIClient

from local_departments.models import Department, Organisation
from metadata.models import Measurement, MeasurementType, MeasurementUnit, NetworkElement, NetworkElementType, PhysicalDevice
from metadata.tests.test_backend import create_catalog

from .models import UserDepartment, UserRole

pytestmark = pytest.mark.django_db
STRONG = "a-long-test-only-passphrase"


@pytest.fixture
def world(settings):
    settings.METADATA_ACCESS_POLICY = "platform_security.access.DepartmentAccessPolicy"
    settings.METADATA_PLATFORM_DEPARTMENT_ID = 1
    return create_catalog()


def login(role, departments=(), username=None):
    user = get_user_model().objects.create_user(username=username or role.lower(), password=STRONG)
    UserRole.objects.create(user=user, role=role)
    for pk in departments:
        UserDepartment.objects.create(user=user, department_id=pk)
    client = APIClient()
    client.force_authenticate(user)
    return client, user


def session_login(role, departments=(), username=None):
    """Real session login, needed for plain Django views (force_authenticate is DRF-only)."""
    _, user = login(role, departments, username)
    client = APIClient()
    client.force_login(user)
    return client, user


def new_user(username="newbie", role="EDITOR", departments=(2,), **extra):
    return {"username": username, "password": STRONG, "role": role, "departments": list(departments), **extra}


def test_system_admin_creates_lists_updates_and_deactivates_users(world):
    client, admin = login("SYSTEM_ADMIN")
    response = client.post("/api/v1/users/", new_user(), format="json")
    assert response.status_code == 201, response.data
    assert "password" not in response.data
    assert response.data["role"] == "EDITOR" and response.data["departments"] == [2]
    user = get_user_model().objects.get(username="newbie")
    assert user.check_password(STRONG)
    rows = client.get("/api/v1/users/").data["results"]
    assert {r["username"] for r in rows} == {"system_admin", "newbie"}
    patched = client.patch(f"/api/v1/users/{user.pk}/", {"role": "VIEWER", "departments": [2, 3]}, format="json")
    assert patched.status_code == 200, patched.data
    assert patched.data["role"] == "VIEWER" and patched.data["departments"] == [2, 3]
    assert client.delete(f"/api/v1/users/{user.pk}/").status_code == 204
    user.refresh_from_db()
    assert user.is_active is False  # logical deletion; the record stays
    assert client.delete(f"/api/v1/users/{admin.pk}/").status_code == 403


def test_user_validation(world):
    client, _ = login("SYSTEM_ADMIN")
    assert client.post("/api/v1/users/", new_user(password="short"), format="json").status_code == 400
    assert client.post("/api/v1/users/", new_user(role="ROOT"), format="json").status_code == 400
    assert client.post("/api/v1/users/", new_user(departments=[999]), format="json").status_code == 400
    assert client.post("/api/v1/users/", {"username": "x", "role": "VIEWER"}, format="json").status_code == 400
    assert client.post("/api/v1/users/", new_user(), format="json").status_code == 201
    assert client.post("/api/v1/users/", new_user(), format="json").status_code == 400  # duplicate username


def test_department_admin_is_limited_to_own_departments_and_lower_roles(world):
    client, _ = login("DEPARTMENT_ADMIN", [2])
    created = client.post("/api/v1/users/", new_user(departments=[2]), format="json")
    assert created.status_code == 201, created.data
    assert client.post("/api/v1/users/", new_user("a", departments=[3]), format="json").status_code == 400
    assert client.post("/api/v1/users/", new_user("b", role="SYSTEM_ADMIN"), format="json").status_code == 400
    assert client.post("/api/v1/users/", new_user("c", role="DEPARTMENT_ADMIN"), format="json").status_code == 400
    _, outsider = login("EDITOR", [3], username="south-editor")
    sysadmin = get_user_model().objects.create_user(username="boss", password=STRONG)
    UserRole.objects.create(user=sysadmin, role="SYSTEM_ADMIN")
    UserDepartment.objects.create(user=sysadmin, department_id=2)
    visible = {r["username"] for r in client.get("/api/v1/users/").data["results"]}
    assert visible == {"newbie"}  # not the other Department's editor, not System Administrators
    assert client.get(f"/api/v1/users/{outsider.pk}/").status_code == 404
    assert client.patch(f"/api/v1/users/{sysadmin.pk}/", {"role": "VIEWER"}, format="json").status_code == 404


def test_department_admin_edit_preserves_memberships_outside_scope(world):
    client, _ = login("DEPARTMENT_ADMIN", [2])
    _, member = login("EDITOR", [2, 3], username="shared")
    response = client.patch(f"/api/v1/users/{member.pk}/", {"departments": []}, format="json")
    assert response.status_code == 200, response.data
    assert set(UserDepartment.objects.filter(user=member).values_list("department_id", flat=True)) == {3}


@pytest.mark.parametrize("role", ["VIEWER", "EDITOR"])
def test_viewers_and_editors_cannot_manage_users(world, role):
    client, _ = login(role, [2])
    assert client.get("/api/v1/users/").status_code == 403
    assert client.post("/api/v1/users/", new_user(), format="json").status_code == 403


def test_users_require_session_and_reject_api_keys_and_no_policy(world, settings):
    assert APIClient().get("/api/v1/users/").status_code in (401, 403)
    _, admin = login("SYSTEM_ADMIN")
    client = APIClient()
    client.force_login(admin)
    assert client.get("/api/v1/users/").status_code == 200
    assert client.get("/api/v1/users/", HTTP_X_API_KEY="smk_" + "0" * 32 + "." + "A" * 43).status_code in (401, 403)
    settings.METADATA_ACCESS_POLICY = "metadata.access.NoAccessPolicy"
    assert client.get("/api/v1/users/").status_code == 403


def test_departments_list_scoped_and_create_restricted_to_system_admin(world):
    editor, _ = login("EDITOR", [2], username="ed")
    rows = editor.get("/api/v1/departments/").data["results"]
    assert [r["id"] for r in rows] == [2] and rows[0]["organisation_code"] == "demo"
    assert editor.post("/api/v1/departments/", {"name": "East", "organisation": 2}, format="json").status_code == 403
    admin, _ = login("SYSTEM_ADMIN")
    with connection.cursor() as cursor:  # fixtures insert explicit IDs; move the sequence past them
        cursor.execute("SELECT setval(pg_get_serial_sequence('local_departments_department','id'), 100)")
    org = Organisation.objects.get(code="demo")
    response = admin.post("/api/v1/departments/", {"name": "East", "organisation": org.pk}, format="json")
    assert response.status_code == 201, response.data
    assert Department.objects.filter(name="East", organisation=org).exists()
    assert admin.post("/api/v1/departments/", {"name": "East", "organisation": org.pk}, format="json").status_code == 400
    assert admin.post("/api/v1/departments/", {"name": "X", "organisation": 9999}, format="json").status_code == 400
    assert len(admin.get("/api/v1/departments/").data["results"]) == 4


def test_devices_alias_matches_physical_devices(world):
    client, _ = login("VIEWER", [2])
    device = PhysicalDevice.objects.create(name="N", department_id=2, device_type_id=world["device_type"])
    PhysicalDevice.objects.create(name="S", department_id=3, device_type_id=world["device_type"])
    ids = [r["id"] for r in client.get("/api/v1/devices/").data["results"]]
    assert ids == [device.pk]
    assert client.get(f"/api/v1/devices/{device.pk}/").status_code == 200


def make_measurement(world, department, config):
    device = PhysicalDevice.objects.create(name=f"d{department}", department_id=department, device_type_id=world["device_type"])
    element = NetworkElement.objects.create(
        name=f"e{department}", department_id=department, element_type=NetworkElementType.objects.get(),
    )
    return Measurement.objects.create(
        name=f"m{department}", department_id=department, physical_device=device, network_element=element,
        measurement_type=MeasurementType.objects.get(), measurement_unit=MeasurementUnit.objects.get(),
        data_collection_config=config,
    )


def test_measurement_configuration_endpoint(world):
    config = {"protocol": "https", "endpoint": "https://example.invalid/c"}
    mine, other = make_measurement(world, 2, config), make_measurement(world, 3, config)
    client, _ = login("VIEWER", [2])
    response = client.get(f"/api/v1/measurements/{mine.pk}/configuration/")
    assert response.status_code == 200 and response.data == config
    assert client.get(f"/api/v1/measurements/{other.pk}/configuration/").status_code == 404
    assert client.post(f"/api/v1/measurements/{mine.pk}/configuration/", {}, format="json").status_code == 405
    stored = mine.collection_configuration
    assert stored.department_id == 2 and stored.config == config
    mine.data_collection_config = None
    mine.save()
    assert client.get(f"/api/v1/measurements/{mine.pk}/configuration/").status_code == 404


def test_openapi_schema_requires_login_and_lists_new_endpoints(world):
    assert APIClient().get("/api/v1/openapi.json").status_code in (401, 403)
    client, _ = login("VIEWER", [2])
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for path in ("/api/v1/users/", "/api/v1/departments/", "/api/v1/physical-devices/", "/api/v1/measurements/{id}/configuration/"):
        assert path in paths
    assert b"SwaggerUIBundle" in client.get("/api/v1/docs/").content


def test_user_changes_own_password_and_stays_signed_in(world):
    client, user = session_login("EDITOR", [2])
    url = "/api/v1/auth/password/"
    ok = {"current_password": STRONG, "new_password": "another-long-passphrase"}
    assert APIClient().post(url, ok, format="json").status_code == 403
    assert client.post(url, {**ok, "current_password": "wrong-wrong-wrong"}, format="json").status_code == 400
    assert client.post(url, {**ok, "new_password": "short"}, format="json").status_code == 400
    assert client.post(url, {**ok, "new_password": STRONG}, format="json").status_code == 400
    assert client.post(url, {"new_password": "another-long-passphrase"}, format="json").status_code == 400
    assert client.post(url, ok, format="json").status_code == 200
    user.refresh_from_db()
    assert user.check_password("another-long-passphrase") and not user.check_password(STRONG)


def test_organisations_list_and_create(world):
    editor, _ = login("EDITOR", [2], username="org-ed")
    assert [o["code"] for o in editor.get("/api/v1/organisations/").data["results"]] == ["demo"]
    assert editor.post("/api/v1/organisations/", {"name": "N", "code": "n"}, format="json").status_code == 403
    admin, _ = login("SYSTEM_ADMIN")
    assert admin.post("/api/v1/organisations/", {"name": "North Water", "code": "north-water"}, format="json").status_code == 201
    assert admin.post("/api/v1/organisations/", {"name": "Dup", "code": "north-water"}, format="json").status_code == 400
    assert admin.post("/api/v1/organisations/", {"name": "Bad", "code": "Bad Code!"}, format="json").status_code == 400
    assert {o["code"] for o in admin.get("/api/v1/organisations/").data["results"]} >= {"platform", "demo", "north-water"}


def client_workbook():
    from metadata.tests.test_backend import make_workbook
    return make_workbook({
        "Measurements": [
            ("Department", "MeasurementId", "MeasurementName", "MeasurementCollectionBatch", "MeasurementType",
             "MeasurementUnit", "Details", "NetworkElementId", "PhysicalDeviceId", "DataCollectionType",
             "DataCollectionParameters"),
            ("North", "M1", "Flow A", 3, "Flow", "m3/h", "main", "NE1", "D1", "MQTT", '{"topic": "a/b"}'),
        ],
        "NetworkElements": [
            ("Department", "NetworkElementId", "NetworkElementName", "NetworkElementType", "NetworkArea",
             "Latitude", "Longitude", "Elevation", "StrategicId", "DMAId", "Address"),
            ("North", "NE1", "Inlet", "DMA_Inlet", "Zone 1", 35.1, 33.3, 120.5, "S1", "DMA1", "1 Main St"),
        ],
        "Physical_devices": [
            ("Department", "Device_id", "Device_name", "Device_type", "CommunicationParameters", "longitude", "latitude"),
            ("North", "D1", "Logger 1", "T64", '{"ip": "10.0.0.1"}', 33.3, 35.1),
        ],
        "Statistics": [("anything",)],
        "LOVs": [("anything",)],
    })


def post_client_file(client):
    return client.post("/api/v1/imports/excel/", {"department": 2, "file": client_workbook()}, format="multipart")


def test_client_format_import_creates_records_and_shared_list_entries(world):
    client, _ = login("SYSTEM_ADMIN")
    response = post_client_file(client)
    assert response.status_code == 201, response.json()
    assert response.json()["created"] == {
        "Physical_devices": 1, "NetworkElements": 1, "Measurements": 1, "New shared list entries": 4}
    measurement = Measurement.objects.get(name="Flow A")
    assert measurement.department_id == 2
    assert measurement.data_collection_config == {
        "source_identifier": "M1", "protocol": "MQTT", "extra_settings": {"topic": "a/b"}, "collection_batch": 3}
    element = NetworkElement.objects.get(name="Inlet")
    assert (element.network_area, element.elevation, element.address) == ("Zone 1", 120.5, "1 Main St")
    assert PhysicalDevice.objects.get(name="Logger 1").communication_parameters == {"ip": "10.0.0.1"}
    # Importing the same file again is refused (identifier already used) and changes nothing.
    again = post_client_file(client)
    assert again.status_code == 400
    assert MeasurementType.objects.filter(name="Flow").count() == 1
    assert Measurement.objects.filter(name="Flow A").count() == 1


def test_client_format_import_rejects_unknown_list_values_for_non_administrators(world):
    client, _ = login("EDITOR", [2])
    response = post_client_file(client)
    assert response.status_code == 400
    assert {e["sheet"] for e in response.json()["errors"]} == {"Physical_devices", "NetworkElements", "Measurements"}
    assert not Measurement.objects.filter(name="Flow A").exists()


def test_client_format_import_rejects_overlong_list_names(world):
    from metadata.tests.test_backend import make_workbook
    client, _ = login("SYSTEM_ADMIN")
    upload = make_workbook({
        "Measurements": [("MeasurementName", "MeasurementType", "MeasurementUnit", "NetworkElementId", "PhysicalDeviceId"),
                         ("m", "x" * 300, "m3/h", "NE1", "D1")],
        "NetworkElements": [("NetworkElementId", "NetworkElementName", "NetworkElementType"), ("NE1", "n", "DMA")],
        "Physical_devices": [("Device_id", "Device_name", "Device_type"), ("D1", "d", "T64")],
    })
    response = client.post("/api/v1/imports/excel/", {"department": 2, "file": upload}, format="multipart")
    assert response.status_code == 400
    assert "MeasurementType" in response.json()["errors"][0]["errors"]
    assert not MeasurementType.objects.filter(name__startswith="xxx").exists()


def test_form_fields_can_be_created_edited_and_cleared_through_the_api(world):
    client, _ = login("EDITOR", [2])
    created = client.post("/api/v1/network-elements/", {
        "name": "Inlet", "department": 2, "element_type": world["element_type"],
        "network_area": "Zone 1", "elevation": 120.5, "address": "1 Main St"}, format="json")
    assert created.status_code == 201, created.data
    assert (created.data["network_area"], created.data["elevation"], created.data["address"]) == ("Zone 1", 120.5, "1 Main St")
    cleared = client.patch(f"/api/v1/network-elements/{created.data['id']}/",
                           {"elevation": None, "network_area": "", "address": ""}, format="json")
    assert cleared.status_code == 200, cleared.data
    assert (cleared.data["elevation"], cleared.data["network_area"], cleared.data["address"]) == (None, "", "")
    device = client.post("/api/v1/physical-devices/", {
        "name": "Logger", "department": 2, "device_type": world["device_type"],
        "communication_parameters": {"ip": "10.0.0.1", "port": 502}}, format="json")
    assert device.status_code == 201, device.data
    assert device.data["communication_parameters"] == {"ip": "10.0.0.1", "port": 502}
    patched = client.patch(f"/api/v1/physical-devices/{device.data['id']}/", {"communication_parameters": None}, format="json")
    assert patched.status_code == 200 and patched.data["communication_parameters"] is None


def reset_url(user):
    return f"/api/v1/users/{user.pk}/reset-password/"


def test_system_admin_resets_a_password_after_confirming_their_own(world):
    from django.test import Client

    admin_client, _ = login("SYSTEM_ADMIN")
    _, target = login("EDITOR", [2], username="teacher")
    target_session = Client()
    target_session.force_login(target)
    assert target_session.get("/api/v1/auth/session/").json()["authenticated"] is True

    wrong = admin_client.post(reset_url(target), {"current_password": "not-my-password"}, format="json")
    assert wrong.status_code == 400
    target.refresh_from_db()
    assert target.check_password(STRONG)  # nothing changed

    response = admin_client.post(reset_url(target), {"current_password": STRONG}, format="json")
    assert response.status_code == 200, response.data
    assert response["Cache-Control"] == "no-store"
    new_password = response.data["password"]
    assert response.data["username"] == "teacher" and len(new_password) >= 12
    target.refresh_from_db()
    assert target.check_password(new_password) and not target.check_password(STRONG)
    # The target's existing sessions end; the password is never returned again.
    assert target_session.get("/api/v1/auth/session/").json()["authenticated"] is False
    listing = admin_client.get("/api/v1/users/")
    assert "password" not in str(listing.data) and new_password not in str(listing.data)
    assert "password" not in admin_client.get(f"/api/v1/users/{target.pk}/").data


def test_password_reset_requires_the_confirmation_password(world):
    client, _ = login("SYSTEM_ADMIN")
    _, target = login("VIEWER", [2], username="viewer1")
    assert client.post(reset_url(target), {}, format="json").status_code == 400
    assert client.post(reset_url(target), {"current_password": ""}, format="json").status_code == 400
    assert client.post(reset_url(target), {"current_password": 12345}, format="json").status_code == 400
    target.refresh_from_db()
    assert target.check_password(STRONG)


def test_only_system_administrators_may_reset_passwords(world):
    _, target = login("VIEWER", [2], username="viewer1")
    for role in ("DEPARTMENT_ADMIN", "EDITOR", "VIEWER"):
        client, _ = login(role, [2], username=f"actor_{role.lower()}")
        response = client.post(reset_url(target), {"current_password": STRONG}, format="json")
        assert response.status_code == 403, role
    anonymous = APIClient()
    assert anonymous.post(reset_url(target), {"current_password": STRONG}, format="json").status_code in (401, 403)
    target.refresh_from_db()
    assert target.check_password(STRONG)


def test_a_system_administrator_cannot_reset_their_own_password_here(world):
    client, admin = login("SYSTEM_ADMIN")
    assert client.post(reset_url(admin), {"current_password": STRONG}, format="json").status_code == 403
    admin.refresh_from_db()
    assert admin.check_password(STRONG)


def test_wrong_confirmation_passwords_are_throttled(world, settings):
    settings.LOGIN_FAILURE_LIMIT = 3
    client, _ = login("SYSTEM_ADMIN")
    _, target = login("EDITOR", [2], username="teacher")
    for _ in range(3):
        assert client.post(reset_url(target), {"current_password": "wrong-password-1"}, format="json").status_code == 400
    blocked = client.post(reset_url(target), {"current_password": STRONG}, format="json")
    assert blocked.status_code == 429 and "Retry-After" in blocked
    target.refresh_from_db()
    assert target.check_password(STRONG)
