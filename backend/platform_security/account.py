"""Own-account endpoint for the Settings page."""

import json

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .admin_api import MIN_PASSWORD_LENGTH


def _json_body(request):
    if request.content_type != "application/json":
        return None
    try:
        body = json.loads(request.body)
    except (ValueError, RecursionError):
        return None
    return body if isinstance(body, dict) else None


@require_POST
@never_cache
@csrf_protect
def change_password(request):
    """Change the signed-in user's own password; other sessions stay valid only for this one."""
    user = request.user
    if not user.is_authenticated or not user.is_active:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=403)
    body = _json_body(request)
    if (
        body is None or body.keys() != {"current_password", "new_password"}
        or not all(isinstance(v, str) for v in body.values())
    ):
        return JsonResponse({"detail": "Provide current_password and new_password."}, status=400)
    current, new = body["current_password"], body["new_password"]
    if "\x00" in new or "\x00" in current:
        return JsonResponse({"detail": "Invalid password."}, status=400)
    if not user.check_password(current):
        return JsonResponse({"current_password": ["The current password is incorrect."]}, status=400)
    if len(new) < MIN_PASSWORD_LENGTH:
        return JsonResponse({"new_password": [f"Use at least {MIN_PASSWORD_LENGTH} characters."]}, status=400)
    if new == current:
        return JsonResponse({"new_password": ["Choose a password different from the current one."]}, status=400)
    try:
        validate_password(new, user)
    except ValidationError as error:
        return JsonResponse({"new_password": list(error.messages)}, status=400)
    user.set_password(new)
    user.save(update_fields=["password"])
    update_session_auth_hash(request, user)  # keep this browser signed in; other sessions end
    return JsonResponse({"ok": True})
