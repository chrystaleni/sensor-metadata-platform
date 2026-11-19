from types import SimpleNamespace

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from local_departments.models import Department
from metadata.access import get_access_policy
from .models import UserRole


@require_GET
@never_cache
def access_context(request):
    user = request.user
    result = {"authenticated": user.is_authenticated, "role": None, "departments": [],
              "permissions": {"write_metadata": False, "manage_catalogs": False, "manage_api_keys": False}}
    if user.is_authenticated and user.is_active:
        role = UserRole.objects.filter(user_id=user.pk).values_list("role", flat=True).first()
        policy = get_access_policy()
        principal = SimpleNamespace(user=user, auth=None)
        readable = set(policy.readable_department_ids(principal))
        writable = set(policy.writable_department_ids(principal))
        result["role"] = role
        result["departments"] = [
            {"id": d.pk, "name": d.name, "organisation": d.organisation.code,
             "writable": d.pk in writable}
            for d in Department.objects.select_related("organisation").filter(pk__in=readable).order_by("id")
        ]
        result["permissions"] = {
            "write_metadata": bool(writable),
            "manage_catalogs": policy.can_manage_controlled_lists(principal),
            "manage_api_keys": bool(writable) and role in (UserRole.Role.SYSTEM_ADMIN, UserRole.Role.DEPARTMENT_ADMIN),
        }
    return JsonResponse(result)
