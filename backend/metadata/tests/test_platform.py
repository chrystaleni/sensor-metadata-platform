from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from local_departments.models import Department, Organisation
from metadata.models import PhysicalDevice
from metadata.platform import CONTROLLED_LISTS

from .test_backend import API, POLICY, create_catalog, make_workbook


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_provisioning_creates_platform_once_with_id_one_occupied(settings):
    settings.METADATA_PLATFORM_DEPARTMENT_ID = None
    Organisation.objects.filter(code="platform").delete()
    ordinary = Organisation.objects.create(code="water", name="Water Services")
    unrelated = Department.objects.create(organisation=ordinary, name="Platform")
    assert unrelated.pk == 1
    outputs = []
    for _ in range(2):
        output = StringIO()
        call_command("provision_platform_department", stdout=output)
        outputs.append(output.getvalue().strip())

    platform = Organisation.objects.get(code="platform", name="Platform").departments.get()
    assert platform.pk != unrelated.pk
    assert outputs == [f"METADATA_PLATFORM_DEPARTMENT_ID={platform.pk}"] * 2
    unrelated.refresh_from_db()
    assert unrelated.organisation_id == ordinary.pk


@pytest.mark.django_db
def test_provisioning_rejects_ambiguous_departments(settings):
    settings.METADATA_PLATFORM_DEPARTMENT_ID = None
    organisation, _ = Organisation.objects.get_or_create(code="platform", defaults={"name": "Platform"})
    organisation.departments.create(name="Platform")
    organisation.departments.create(name="Shared Reference Data")

    with pytest.raises(CommandError, match="Multiple Departments"):
        call_command("provision_platform_department")

    assert organisation.departments.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize("configured_id", [None, 999, 3])
def test_invalid_configuration_blocks_catalog_access_and_metadata_writes(settings, configured_id):
    settings.METADATA_PLATFORM_DEPARTMENT_ID = configured_id
    settings.METADATA_ACCESS_POLICY = POLICY
    catalog = create_catalog()
    users = get_user_model().objects
    editor = users.create_user(username="editor")
    manager = users.create_user(username="catalog-manager")
    client = APIClient()
    client.force_authenticate(manager)
    assert client.get(f"{API}measurement-types/").status_code == 403
    assert client.post(f"{API}measurement-types/", {"name": "Blocked"}, format="json").status_code == 403

    client.force_authenticate(editor)
    response = client.post(f"{API}physical-devices/", {
        "department": 2, "name": "Blocked", "device_type": catalog["device_type"],
    }, format="json")
    assert response.status_code == 400
    assert "device_type" in response.json()
    workbook = make_workbook({
        "Physical Devices": [("name", "device_type"), ("Blocked", catalog["device_type"])],
    })
    response = client.post(f"{API}imports/excel/", {"department": 2, "file": workbook}, format="multipart")
    assert response.status_code == 400
    assert "device_type" in response.json()["errors"][0]["errors"]


@pytest.mark.django_db
@pytest.mark.parametrize("catalog_model", CONTROLLED_LISTS)
def test_provisioning_and_catalog_access_reject_conflicting_ownership(settings, catalog_model):
    settings.METADATA_PLATFORM_DEPARTMENT_ID = 1
    settings.METADATA_ACCESS_POLICY = POLICY
    create_catalog()
    rogue = catalog_model.objects.create(name="Conflicting", department_id=3)
    with pytest.raises(CommandError, match="conflicting Department ownership"):
        call_command("provision_platform_department")

    client = APIClient()
    client.force_authenticate(get_user_model().objects.create_user(username="catalog-manager"))
    assert client.get(f"{API}measurement-types/").status_code == 403
    rogue.refresh_from_db()
    assert rogue.department_id == 3
    assert Department.objects.count() == 3


@pytest.mark.django_db
def test_provisioning_preserves_existing_renamed_owner_and_metadata(settings):
    settings.METADATA_PLATFORM_DEPARTMENT_ID = None
    catalog = create_catalog()
    platform = Department.objects.get(pk=1)
    platform.name = "Shared Reference Data"
    platform.save(update_fields=["name"])
    device = PhysicalDevice.objects.create(department_id=2, name="Meter", device_type_id=catalog["device_type"])
    output = StringIO()
    call_command("provision_platform_department", stdout=output)

    assert output.getvalue().strip() == f"METADATA_PLATFORM_DEPARTMENT_ID={platform.pk}"
    device.refresh_from_db()
    assert device.department_id == 2
    assert device.device_type_id == catalog["device_type"]
    assert device.device_type.department_id == platform.pk
    platform.refresh_from_db()
    assert platform.name == "Shared Reference Data"
