from local_departments.models import Department
from metadata.access import get_access_policy
from platform_security.models import UserRole


def managed_departments(user):
    if not user.is_authenticated or not user.is_active:
        return Department.objects.none()
    role = UserRole.objects.filter(user_id=user.pk).values_list("role", flat=True).first()
    if role not in (UserRole.Role.SYSTEM_ADMIN, UserRole.Role.DEPARTMENT_ADMIN):
        return Department.objects.none()
    # The configured metadata adapter remains authoritative, including NoAccessPolicy.
    from types import SimpleNamespace
    scope = get_access_policy().writable_department_ids(SimpleNamespace(user=user, auth=None))
    return Department.objects.filter(pk__in=scope)
