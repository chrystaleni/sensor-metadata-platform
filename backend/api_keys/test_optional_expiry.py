"""API keys may have no expiration (Phase 2, 1.4.4); expired keys can still be revoked (Figure 44)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from api_keys.models import APIKey
from platform_security.test_admin_api import login, world  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db


def test_key_without_expiration_works_until_revoked(world):
    admin, _ = login("DEPARTMENT_ADMIN", (2,))
    created = admin.post("/api/v1/api-keys/", {"name": "SCADA", "department": 2, "expires_at": None}, format="json")
    assert created.status_code == 201, created.content
    assert created.json()["expires_at"] is None
    key = APIKey.objects.get(pk=created.json()["id"])
    assert key.expires_at is None and not key.is_expired()

    from rest_framework.test import APIClient
    external = APIClient()
    raw = created.json()["key"]
    assert external.get("/api/v1/measurements/", {"department": 2}, HTTP_X_API_KEY=raw).status_code == 200
    assert admin.delete(f"/api/v1/api-keys/{key.pk}/").status_code == 204
    assert external.get("/api/v1/measurements/", {"department": 2}, HTTP_X_API_KEY=raw).status_code == 401


def test_omitted_expiration_still_defaults_to_90_days(world):
    admin, _ = login("DEPARTMENT_ADMIN", (2,))
    created = admin.post("/api/v1/api-keys/", {"name": "Default", "department": 2}, format="json").json()
    expires = APIKey.objects.get(pk=created["id"]).expires_at
    assert timedelta(days=89) < expires - timezone.now() <= timedelta(days=90)


def test_expired_key_can_be_revoked(world):
    admin, user = login("DEPARTMENT_ADMIN", (2,))
    from local_departments.models import Department
    key, _ = APIKey.issue(name="Old", department=Department.objects.get(pk=2), creator=user,
                          expires_at=timezone.now() + timedelta(days=1))
    APIKey.objects.filter(pk=key.pk).update(expires_at=timezone.now() - timedelta(days=1))
    assert admin.delete(f"/api/v1/api-keys/{key.pk}/").status_code == 204
    assert APIKey.objects.get(pk=key.pk).revoked_at is not None
