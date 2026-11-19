import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from metadata.tests.test_backend import create_catalog
from .models import UserRole,UserDepartment

pytestmark=pytest.mark.django_db


def test_operator_assignment_preserves_memberships_and_department_ids():
    create_catalog();user=get_user_model().objects.create_user(username='operator-target')
    UserDepartment.objects.create(user=user,department_id=2)
    call_command('configure_platform_user','operator-target',role='EDITOR',department=[3],create=False)
    assert UserRole.objects.get(user=user).role=='EDITOR'
    assert set(UserDepartment.objects.filter(user=user).values_list('department_id',flat=True))=={2,3}
    user.refresh_from_db();assert not user.is_superuser and not user.is_staff


def test_invalid_membership_does_not_partially_assign_a_role():
    create_catalog();user=get_user_model().objects.create_user(username='operator-target')
    with pytest.raises(CommandError):
        call_command('configure_platform_user','operator-target',role='SYSTEM_ADMIN',department=[99999],create=False)
    assert not UserRole.objects.filter(user=user).exists()
