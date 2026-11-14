import pytest
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
