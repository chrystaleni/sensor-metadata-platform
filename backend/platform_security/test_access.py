import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from local_departments.models import Department, Organisation
from metadata.models import PhysicalDevice, PhysicalDeviceType
from metadata.tests.test_backend import create_catalog, make_workbook

from .models import UserDepartment, UserRole


pytestmark = pytest.mark.django_db
DEVICES = "/api/v1/physical-devices/"


@pytest.fixture
def api(settings):
    settings.METADATA_ACCESS_POLICY = "platform_security.access.DepartmentAccessPolicy"
    settings.METADATA_PLATFORM_DEPARTMENT_ID = 1
    catalog = create_catalog()
    north = PhysicalDevice.objects.create(department_id=2, name="North", device_type_id=catalog["device_type"])
    south = PhysicalDevice.objects.create(department_id=3, name="South", device_type_id=catalog["device_type"])
    return APIClient(), north, south


def authenticate(client, role=None, departments=(), **user_flags):
    user = get_user_model().objects.create_user(username="member", **user_flags)
    if role is not None:
        UserRole.objects.create(user=user, role=role)
    for department_id in departments:
        UserDepartment.objects.create(user=user, department_id=department_id)
    client.force_authenticate(user)
    return user


def detail(device):
    return f"{DEVICES}{device.pk}/"


def create_device(client, reference, department_id):
    return client.post(DEVICES, {
        "department": department_id, "name": "New device", "device_type": reference.device_type_id,
    }, format="json")


def visible_ids(client):
    response = client.get(DEVICES)
    assert response.status_code == 200
    return {row["id"] for row in response.json()["results"]}


def test_anonymous_cannot_access_metadata(api):
    client, north, _ = api
    assert client.get(DEVICES).status_code == 403
    assert client.get(detail(north)).status_code == 403
    assert create_device(client, north, 2).status_code == 403


@pytest.mark.parametrize("departments,user_flags", [
    ((), {}),
    ((2,), {}),
    ((2,), {"is_staff": True, "is_superuser": True}),
])
def test_roleless_users_have_no_metadata_access(api, departments, user_flags):
    client, north, _ = api
    authenticate(client, departments=departments, **user_flags)
    assert visible_ids(client) == set()
    assert client.get(detail(north)).status_code == 404
    assert create_device(client, north, 2).status_code == 403


def test_inactive_user_with_explicit_system_role_has_no_scope(api):
    client, north, _ = api
    authenticate(client, UserRole.Role.SYSTEM_ADMIN, [2], is_active=False)
    assert visible_ids(client) == set()
    assert create_device(client, north, 2).status_code == 403


def test_viewer_can_read_but_cannot_write_or_import(api):
    client, north, south = api
    authenticate(client, UserRole.Role.VIEWER, [2])
    assert visible_ids(client) == {north.pk}
    assert client.get(detail(north)).status_code == 200
    assert client.get(detail(south)).status_code == 404
    assert create_device(client, north, 2).status_code == 403
    assert client.patch(detail(north), {"name": "Blocked"}, format="json").status_code == 403
    assert client.delete(detail(north)).status_code == 403
    workbook = make_workbook({"Physical Devices": [
        ("name", "device_type"), ("Imported", north.device_type_id),
    ]})
    assert client.post("/api/v1/imports/excel/", {
        "department": 2, "file": workbook,
    }, format="multipart").status_code == 403
    north.refresh_from_db()
    assert north.name == "North"
    assert north.deleted_at is None
    assert PhysicalDevice.objects.count() == 2


@pytest.mark.parametrize("role", [UserRole.Role.EDITOR, UserRole.Role.DEPARTMENT_ADMIN])
def test_department_writers_are_scoped_to_memberships(api, role):
    client, north, south = api
    authenticate(client, role, [2], is_staff=True, is_superuser=True)
    assert visible_ids(client) == {north.pk}
    assert client.get(detail(north)).status_code == 200
    assert client.get(detail(south)).status_code == 404
    assert client.patch(detail(south), {"name": "Blocked"}, format="json").status_code == 404
    assert client.delete(detail(south)).status_code == 404
    assert create_device(client, north, 3).status_code == 403
    assert create_device(client, north, 2).status_code == 201
    assert client.patch(detail(north), {"name": "Updated"}, format="json").status_code == 200
    assert client.delete(detail(north)).status_code == 204
    south.refresh_from_db()
    assert south.name == "South"
    assert south.deleted_at is None


def test_explicit_system_admin_access_crosses_departments_without_memberships(api):
    client, north, south = api
    authenticate(client, UserRole.Role.SYSTEM_ADMIN)
    assert visible_ids(client) == {north.pk, south.pk}
    assert create_device(client, north, 3).status_code == 201
    assert client.patch(detail(south), {"name": "Updated"}, format="json").status_code == 200
    assert client.delete(detail(north)).status_code == 204


def test_multi_department_access_reassignment_denial_and_membership_removal(api):
    client, north, south = api
    user = authenticate(client, UserRole.Role.EDITOR, [2, 3])
    assert visible_ids(client) == {north.pk, south.pk}
    response = client.patch(detail(north), {"department": 3}, format="json")
    assert response.status_code == 400
    assert "department" in response.json()
    north.refresh_from_db()
    assert north.department_id == 2

    user.department_memberships.filter(department_id=3).delete()
    assert visible_ids(client) == {north.pk}
    assert client.patch(detail(south), {"name": "Blocked"}, format="json").status_code == 404
    assert create_device(client, north, 3).status_code == 403


def test_role_changes_take_effect_for_same_authenticated_user(api):
    client, north, _ = api
    user = authenticate(client, UserRole.Role.EDITOR, [2])
    assert user.platform_role.role == UserRole.Role.EDITOR
    assert client.patch(detail(north), {"name": "Updated"}, format="json").status_code == 200

    UserRole.objects.filter(user=user).update(role=UserRole.Role.VIEWER)
    assert client.get(detail(north)).status_code == 200
    assert client.patch(detail(north), {"name": "Blocked"}, format="json").status_code == 403

    UserRole.objects.filter(user=user).delete()
    assert client.get(detail(north)).status_code == 404
    assert user.department_memberships.filter(department_id=2).exists()


CATALOGS = ("measurement-types", "measurement-units", "physical-device-types", "network-element-types")


@pytest.mark.parametrize("role", [UserRole.Role.VIEWER, UserRole.Role.EDITOR])
def test_department_role_reads_catalogs_with_membership_but_cannot_mutate(api, role):
    client, _, _ = api
    user = authenticate(client, role, [2], is_staff=True, is_superuser=True)
    for resource in CATALOGS:
        url = f"/api/v1/{resource}/"
        response = client.get(url)
        assert response.status_code == 200
        item_url = f"{url}{response.json()['results'][0]['id']}/"
        assert client.post(url, {"name": "Blocked"}, format="json").status_code == 403
        assert client.patch(item_url, {"name": "Blocked"}, format="json").status_code == 403
        assert client.delete(item_url).status_code == 403
    user.department_memberships.all().delete()
    for resource in CATALOGS:
        assert client.get(f"/api/v1/{resource}/").json()["count"] == 0


@pytest.mark.parametrize("role", [UserRole.Role.DEPARTMENT_ADMIN, UserRole.Role.SYSTEM_ADMIN])
def test_department_and_system_admins_manage_catalogs(api, role):
    client, _, _ = api
    authenticate(client, role, [2])
    for resource in CATALOGS:
        url = f"/api/v1/{resource}/"
        created = client.post(url, {"department": 1, "name": f"Admin {role}"}, format="json")
        assert created.status_code == 201, created.content
        item_url = f"{url}{created.json()['id']}/"
        assert client.patch(item_url, {"description": "edited"}, format="json").status_code == 200
        assert client.delete(item_url).status_code == 204


@pytest.mark.parametrize(("role", "flags", "list_status", "detail_status"), [
    (None, None, 403, 403),
    (None, {}, 200, 404),
    (UserRole.Role.SYSTEM_ADMIN, {"is_active": False}, 200, 404),
])
def test_catalog_access_denied_without_active_platform_role(api, role, flags, list_status, detail_status):
    client, north, _ = api
    if flags is not None:
        authenticate(client, role, [2], **flags)
    url = "/api/v1/physical-device-types/"
    item = f"{url}{north.device_type_id}/"
    response = client.get(url)
    assert response.status_code == list_status
    if list_status == 200:
        assert response.json()["count"] == 0
    assert client.get(item).status_code == detail_status
    assert client.post(url, {"name": "Blocked"}, format="json").status_code == 403
    assert client.patch(item, {"name": "Blocked"}, format="json").status_code == 403
    assert client.delete(item).status_code == 403


def test_system_admin_without_memberships_manages_all_catalogs_at_non_default_id(settings):
    settings.METADATA_ACCESS_POLICY = "platform_security.access.DepartmentAccessPolicy"
    settings.METADATA_PLATFORM_DEPARTMENT_ID = 83
    platform, _ = Organisation.objects.get_or_create(code="platform", defaults={"name": "Platform"})
    Department.objects.create(pk=83, name="Catalogs", organisation=platform)
    other = Organisation.objects.create(code="water", name="Water")
    Department.objects.create(pk=1, name="Platform", organisation=other)
    client = APIClient()
    user = authenticate(client, UserRole.Role.SYSTEM_ADMIN)
    assert not user.department_memberships.exists()

    for resource in CATALOGS:
        url = f"/api/v1/{resource}/"
        assert client.get(url).status_code == 200
        response = client.post(url, {"name": "Shared value", "department": 1}, format="json")
        assert response.status_code == 201
        assert response.json()["department"] == 83
        item = f"{url}{response.json()['id']}/"
        assert client.get(item).status_code == 200
        response = client.patch(item, {"name": "Updated value", "department": 1}, format="json")
        assert response.status_code == 200
        assert response.json()["name"] == "Updated value"
        assert response.json()["department"] == 83
        assert client.post(url, {"name": "UPDATED VALUE"}, format="json").status_code == 400
        assert client.delete(item).status_code == 204
        assert client.get(item).status_code == 404
        archived = client.get(f"{item}?include_inactive=true")
        assert archived.status_code == 200
        assert archived.json()["department"] == 83


@pytest.mark.parametrize("configured_id", [None, 999, 2, 1])
def test_system_admin_catalog_mutations_fail_closed_with_invalid_owner(api, settings, configured_id):
    client, north, _ = api
    authenticate(client, UserRole.Role.SYSTEM_ADMIN)
    settings.METADATA_PLATFORM_DEPARTMENT_ID = configured_id
    if configured_id == 1:
        PhysicalDeviceType.objects.create(name="Wrong owner", department_id=2)
    url = "/api/v1/physical-device-types/"
    item = f"{url}{north.device_type_id}/"
    assert client.get(url).status_code == 403
    assert client.post(url, {"name": "Blocked"}, format="json").status_code == 403
    assert client.patch(item, {"name": "Blocked"}, format="json").status_code == 403
    assert client.delete(item).status_code == 403
    entry = PhysicalDeviceType.objects.get(pk=north.device_type_id)
    assert entry.name == "Weather station"
    assert entry.department_id == 1
    assert entry.deleted_at is None


def test_system_admin_cannot_archive_catalog_entry_with_active_dependents(api):
    client, north, _ = api
    authenticate(client, UserRole.Role.SYSTEM_ADMIN)
    item = f"/api/v1/physical-device-types/{north.device_type_id}/"
    assert client.delete(item).status_code == 409
    assert client.get(item).status_code == 200


def test_default_policy_denies_even_explicit_system_admin(api, settings):
    client, north, _ = api
    settings.METADATA_ACCESS_POLICY = "metadata.access.NoAccessPolicy"
    authenticate(client, UserRole.Role.SYSTEM_ADMIN, [2])
    assert visible_ids(client) == set()
    assert client.get(detail(north)).status_code == 404
    assert create_device(client, north, 2).status_code == 403
    catalog = "/api/v1/physical-device-types/"
    assert client.get(catalog).json()["count"] == 0
    assert client.post(catalog, {"name": "Blocked"}, format="json").status_code == 403
