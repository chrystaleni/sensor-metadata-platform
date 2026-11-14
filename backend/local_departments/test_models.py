import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from local_departments.models import Department, Organisation


@pytest.mark.django_db
def test_organisation_creation():
    organisation = Organisation.objects.create(name="Water Services", code="water")

    assert Organisation.objects.get(code="water").pk == organisation.pk
    assert str(organisation) == "Water Services"


@pytest.mark.django_db
def test_organisation_code_is_unique():
    Organisation.objects.create(name="Water Services", code="water")

    with pytest.raises(IntegrityError), transaction.atomic():
        Organisation.objects.create(name="Other Services", code="water")


@pytest.mark.django_db
def test_department_organisation_relationship_is_protected():
    organisation = Organisation.objects.create(name="Water Services", code="water")
    department = Department.objects.create(name="North", organisation=organisation)

    department.refresh_from_db()
    assert department.organisation == organisation
    assert organisation.departments.get() == department
    with pytest.raises(ProtectedError):
        organisation.delete()


@pytest.mark.django_db
def test_department_requires_organisation():
    with pytest.raises(IntegrityError), transaction.atomic():
        Department.objects.create(name="North")


@pytest.mark.django_db
def test_department_name_is_unique_within_organisation_only():
    water = Organisation.objects.create(name="Water Services", code="water")
    regional = Organisation.objects.create(name="Regional Authority", code="regional")
    Department.objects.create(name="North", organisation=water)
    Department.objects.create(name="North", organisation=regional)
    Department.objects.create(name="north", organisation=water)

    with pytest.raises(IntegrityError), transaction.atomic():
        Department.objects.create(name="North", organisation=water)


@pytest.mark.django_db
def test_demo_fixtures_reuse_platform_organisation_by_code():
    Organisation.objects.filter(code="platform").delete()
    platform = Organisation.objects.create(pk=83, code="platform", name="Platform")

    call_command("loaddata", "demo_departments", verbosity=0)

    assert Department.objects.get(pk=1).organisation_id == platform.pk
    assert Department.objects.get(pk=2).organisation.code == "demo"
