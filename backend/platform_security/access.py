from local_departments.models import Department
from metadata.access import NoAccessPolicy

from .models import UserDepartment, UserRole


class DepartmentAccessPolicy(NoAccessPolicy):
    """Resolve operational access from current role and membership rows."""

    def readable_department_ids(self, request):
        return self._department_ids(request, write=False)

    def writable_department_ids(self, request):
        return self._department_ids(request, write=True)

    def _department_ids(self, request, *, write):
        user = request.user
        if not user.is_authenticated or not user.is_active:
            return ()

        role = UserRole.objects.filter(user_id=user.pk).values_list("role", flat=True).first()
        if role == UserRole.Role.SYSTEM_ADMIN:
            return Department.objects.values_list("pk", flat=True)

        allowed = {UserRole.Role.EDITOR, UserRole.Role.DEPARTMENT_ADMIN}
        if not write:
            allowed.add(UserRole.Role.VIEWER)
        if role not in allowed:
            return ()

        return UserDepartment.objects.filter(user_id=user.pk).values_list("department_id", flat=True)
