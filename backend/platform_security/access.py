from local_departments.models import Department
from metadata.access import NoAccessPolicy

from .models import UserDepartment, UserRole


class DepartmentAccessPolicy(NoAccessPolicy):
    """Resolve metadata access from current role and membership rows."""

    def readable_department_ids(self, request):
        return self._department_ids(request, write=False)

    def writable_department_ids(self, request):
        return self._department_ids(request, write=True)

    def can_manage_controlled_lists(self, request):
        return self._role(request) == UserRole.Role.SYSTEM_ADMIN

    def _role(self, request):
        user = request.user
        if not user.is_authenticated or not user.is_active:
            return None

        return UserRole.objects.filter(user_id=user.pk).values_list("role", flat=True).first()

    def _department_ids(self, request, *, write):
        role = self._role(request)
        if role == UserRole.Role.SYSTEM_ADMIN:
            return Department.objects.values_list("pk", flat=True)

        allowed = {UserRole.Role.EDITOR, UserRole.Role.DEPARTMENT_ADMIN}
        if not write:
            allowed.add(UserRole.Role.VIEWER)
        if role not in allowed:
            return ()

        return UserDepartment.objects.filter(user_id=request.user.pk).values_list("department_id", flat=True)
