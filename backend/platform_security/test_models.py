import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from local_departments.models import Department, Organisation

from .models import UserDepartment


pytestmark = pytest.mark.django_db


@pytest.fixture
def membership():
    user = get_user_model().objects.create_user(username="member")
    organisation = Organisation.objects.create(code="water", name="Water Services")
    department = Department.objects.create(name="Operations", organisation=organisation)
    return UserDepartment.objects.create(user=user, department=department)


def test_user_can_belong_to_multiple_departments(membership):
    organisation = Organisation.objects.create(code="regional", name="Regional Authority")
    department = Department.objects.create(name="Operations", organisation=organisation)
    membership.user.department_memberships.create(department=department)

    assert set(membership.user.department_memberships.values_list(
        "department_id", "department__organisation__code"
    )) == {
        (membership.department_id, "water"),
        (department.pk, "regional"),
    }


def test_department_can_have_multiple_users(membership):
    other_user = get_user_model().objects.create_user(username="other-member")
    membership.department.user_memberships.create(user=other_user)

    assert set(membership.department.user_memberships.values_list("user_id", flat=True)) == {
        membership.user_id, other_user.pk,
    }


def test_duplicate_membership_is_rejected(membership):
    with pytest.raises(IntegrityError), transaction.atomic():
        UserDepartment.objects.create(user=membership.user, department=membership.department)


def test_deleting_membership_preserves_user_and_department(membership):
    user, department = membership.user, membership.department

    membership.delete()

    user.refresh_from_db()
    department.refresh_from_db()
    assert not user.department_memberships.exists()
    assert department.organisation.code == "water"


def test_deleting_user_removes_membership_and_preserves_department(membership):
    membership_id = membership.pk
    department = membership.department

    membership.user.delete()

    assert not UserDepartment.objects.filter(pk=membership_id).exists()
    department.refresh_from_db()


def test_department_with_membership_is_protected_from_deletion(membership):
    with pytest.raises(ProtectedError):
        membership.department.delete()

    membership.refresh_from_db()
    membership.department.refresh_from_db()
