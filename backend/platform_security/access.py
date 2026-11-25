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
        # Department and System Administrators add, edit, archive, restore and delete shared list entries.
        return not self._api_key(request) and self._role(request) in (
            UserRole.Role.SYSTEM_ADMIN, UserRole.Role.DEPARTMENT_ADMIN,
        )

    def archive_manager_department_ids(self, request):
        if self._api_key(request):
            return ()
        role = self._role(request)
        if role == UserRole.Role.SYSTEM_ADMIN:
            return Department.objects.values_list("pk", flat=True)
        if role == UserRole.Role.DEPARTMENT_ADMIN:
            return UserDepartment.objects.filter(user_id=request.user.pk).values_list("department_id", flat=True)
        return ()

    @staticmethod
    def _api_key(request):
        from api_keys.models import APIKey
        value = getattr(request, "auth", None)
        return value if isinstance(value, APIKey) else None

    def _role(self, request):
        user = request.user
        if not user.is_authenticated or not user.is_active:
            return None

        return UserRole.objects.filter(user_id=user.pk).values_list("role", flat=True).first()

    def _department_ids(self, request, *, write):
        role = self._role(request)
        key = self._api_key(request)
        if key and write:
            return ()
        if role == UserRole.Role.SYSTEM_ADMIN:
            return Department.objects.filter(pk=key.department_id).values_list("pk", flat=True) if key else Department.objects.values_list("pk", flat=True)

        allowed = {UserRole.Role.EDITOR, UserRole.Role.DEPARTMENT_ADMIN}
        if not write:
            allowed.add(UserRole.Role.VIEWER)
        if role not in allowed:
            return ()

        memberships = UserDepartment.objects.filter(user_id=request.user.pk)
        if key:
            memberships = memberships.filter(department_id=key.department_id)
        return memberships.values_list("department_id", flat=True)
