"""System Administrators only: reactivate and delete users, delete empty Departments/Organisations and old API keys."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from api_keys.models import APIKey
from local_departments.models import Department, Organisation
from metadata.models import PhysicalDevice

from .models import UserDepartment, UserRole
from .test_admin_api import login, world  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db
NON_SYSTEM = (("DEPARTMENT_ADMIN", (2,)), ("EDITOR", (2,)), ("VIEWER", (2,)))


def other_user(active=False, departments=(2,)):
    user = get_user_model().objects.create_user(username="target", is_active=active)
    UserRole.objects.create(user=user, role="EDITOR")
    for pk in departments:
        UserDepartment.objects.create(user=user, department_id=pk)
    return user


def test_system_admin_reactivates_and_deletes_a_deactivated_user(world):
    client, _ = login("SYSTEM_ADMIN")
    user = other_user(active=False)
    PhysicalDevice.objects.create(department_id=2, name="Kept", device_type_id=world["device_type"], created_by=user)
    assert client.post(f"/api/v1/users/{user.pk}/reactivate/").status_code == 200
    user.refresh_from_db()
    assert user.is_active
    assert client.delete(f"/api/v1/users/{user.pk}/purge/").status_code == 409  # still active
    assert client.delete(f"/api/v1/users/{user.pk}/").status_code == 204  # deactivate
    assert client.delete(f"/api/v1/users/{user.pk}/purge/").status_code == 204
    assert not get_user_model().objects.filter(pk=user.pk).exists()
    assert PhysicalDevice.objects.get(name="Kept").created_by is None  # records stay


def test_system_admin_cannot_delete_themselves(world):
    client, me = login("SYSTEM_ADMIN")
    assert client.delete(f"/api/v1/users/{me.pk}/purge/").status_code == 403


@pytest.mark.parametrize(("role", "departments"), NON_SYSTEM)
def test_other_roles_cannot_reactivate_or_delete_users(world, role, departments):
    client, _ = login(role, departments)
    user = other_user(active=False)
    assert client.post(f"/api/v1/users/{user.pk}/reactivate/").status_code == 403
    assert client.delete(f"/api/v1/users/{user.pk}/purge/").status_code == 403
    assert client.patch(f"/api/v1/users/{user.pk}/", {"is_active": True}, format="json").status_code == 403
    user.refresh_from_db()
    assert not user.is_active


def test_system_admin_deletes_only_empty_departments_and_organisations(world):
    client, _ = login("SYSTEM_ADMIN")
    org = Organisation.objects.create(code="spare", name="Spare")
    empty = Department.objects.create(name="Empty", organisation=org)
    assert client.delete(f"/api/v1/organisations/{org.pk}/").status_code == 409  # still has a Department
    assert client.delete(f"/api/v1/departments/{empty.pk}/").status_code == 204
    assert client.delete(f"/api/v1/organisations/{org.pk}/").status_code == 204
    assert not Organisation.objects.filter(pk=org.pk).exists()

    PhysicalDevice.objects.create(department_id=2, name="In use", device_type_id=world["device_type"])
    used = client.delete("/api/v1/departments/2/")
    assert used.status_code == 409
    assert "1 physical devices" in used.json()["detail"]
    assert client.delete("/api/v1/departments/1/").status_code == 409  # Platform
    platform = Organisation.objects.get(code="platform")
    assert client.delete(f"/api/v1/organisations/{platform.pk}/").status_code == 409


def test_department_with_members_or_keys_is_kept(world):
    client, admin = login("SYSTEM_ADMIN")
    other_user(active=True, departments=(3,))
    assert client.delete("/api/v1/departments/3/").status_code == 409
    UserDepartment.objects.filter(department_id=3).delete()
    APIKey.issue(name="k", department=Department.objects.get(pk=3), creator=admin,
                 expires_at=timezone.now() + timedelta(days=1))
    assert client.delete("/api/v1/departments/3/").status_code == 409


@pytest.mark.parametrize(("role", "departments"), NON_SYSTEM)
def test_other_roles_cannot_delete_departments_or_organisations(world, role, departments):
    client, _ = login(role, departments)
    org = Organisation.objects.create(code="spare", name="Spare")
    empty = Department.objects.create(name="Empty", organisation=org)
    assert client.delete(f"/api/v1/departments/{empty.pk}/").status_code in (403, 404)
    assert client.delete(f"/api/v1/organisations/{org.pk}/").status_code in (403, 404)
    assert Department.objects.filter(pk=empty.pk).exists() and Organisation.objects.filter(pk=org.pk).exists()


def test_system_admin_deletes_only_revoked_or_expired_api_keys(world):
    client, admin = login("SYSTEM_ADMIN")
    department = Department.objects.get(pk=2)
    live, _ = APIKey.issue(name="live", department=department, creator=admin, expires_at=timezone.now() + timedelta(days=1))
    assert client.delete(f"/api/v1/api-keys/{live.pk}/purge/").status_code == 409
    assert client.delete(f"/api/v1/api-keys/{live.pk}/").status_code == 204  # revoke
    assert client.delete(f"/api/v1/api-keys/{live.pk}/purge/").status_code == 204
    expired, _ = APIKey.issue(name="old", department=department, creator=admin, expires_at=timezone.now() + timedelta(days=1))
    APIKey.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(days=1))
    assert client.delete(f"/api/v1/api-keys/{expired.pk}/purge/").status_code == 204
    assert not APIKey.objects.exists()


def test_department_admin_revokes_but_cannot_delete_api_keys(world):
    client, admin = login("DEPARTMENT_ADMIN", (2,))
    key, _ = APIKey.issue(name="k", department=Department.objects.get(pk=2), creator=admin,
                          expires_at=timezone.now() + timedelta(days=1))
    assert client.delete(f"/api/v1/api-keys/{key.pk}/").status_code == 204
    assert client.delete(f"/api/v1/api-keys/{key.pk}/purge/").status_code == 403
    assert APIKey.objects.filter(pk=key.pk).exists()
