import json
import logging

from django.contrib import auth
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .login_throttle import LoginThrottled, LoginThrottleUnavailable, authenticate_with_throttle

# Authentication events go to the application log (Phase 2, scenario S4). Passwords are never logged.
logger = logging.getLogger("platform_security.auth")


def _log_name(username):
    """A username safe for one log line: printable characters only, at most 150."""
    return "".join(ch if ch.isprintable() else "?" for ch in username[:150])


def _client(request):
    return request.META.get("REMOTE_ADDR", "unknown")


def session_response(user):
    return JsonResponse({
        "authenticated": user.is_authenticated,
        "user": {"id": user.pk, "username": user.get_username()} if user.is_authenticated else None,
    })


@require_GET
@never_cache
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"ok": True})


@require_POST
@never_cache
@csrf_protect
def login(request):
    if request.content_type != "application/json":
        return JsonResponse({"detail": "Expected application/json."}, status=415)
    try:
        credentials = json.loads(request.body)
    except (ValueError, RecursionError):
        credentials = None

    if (
        not isinstance(credentials, dict)
        or credentials.keys() != {"username", "password"}
        or not all(isinstance(value, str) for value in credentials.values())
    ):
        return JsonResponse({"detail": "Provide a username and password."}, status=400)

    username, password = credentials["username"], credentials["password"]
    # Reject values that cannot be sent to PostgreSQL or encoded by the password hasher.
    try:
        username.encode("utf-8")
        password.encode("utf-8")
    except UnicodeEncodeError:
        return JsonResponse({"detail": "Invalid username or password."}, status=400)
    if "\x00" in username:
        return JsonResponse({"detail": "Invalid username or password."}, status=400)

    try:
        user = authenticate_with_throttle(request, username, password)
    except LoginThrottled as error:
        logger.warning("Login throttled for username=%r from %s", _log_name(username), _client(request))
        return JsonResponse(
            {"detail": "Too many login attempts. Try again later."},
            status=429,
            headers={"Retry-After": str(error.retry_after)},
        )
    except LoginThrottleUnavailable:
        return JsonResponse(
            {"detail": "Login is temporarily unavailable."},
            status=503,
            headers={"Retry-After": "1"},
        )
    if user is None:
        # Wrong password, unknown username or deactivated account: the same generic answer, one log line.
        logger.warning("Failed login for username=%r from %s", _log_name(username), _client(request))
        return JsonResponse({"detail": "Invalid username or password."}, status=400)
    logger.info("Login of user %s from %s", user.pk, _client(request))
    previous_key = request.session.session_key
    auth.login(request, user)
    if previous_key and request.session.session_key == previous_key:
        # Django keeps the key when the same user signs in again.
        request.session.cycle_key()
    return session_response(user)


@require_GET
@never_cache
def session(request):
    return session_response(request.user)


@require_POST
@never_cache
@csrf_protect
def logout(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=403)
    user_id = request.user.pk
    auth.logout(request)
    logger.info("Logout of user %s", user_id)
    return session_response(request.user)
