from datetime import timedelta
from ipaddress import IPv6Address, ip_address
from math import ceil

from django.conf import settings
from django.contrib import auth
from django.db import InterfaceError, OperationalError, ProgrammingError, connection, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import LoginAttemptWindow


class LoginThrottled(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after


class LoginThrottleUnavailable(Exception):
    pass


def client_key(request):
    try:
        address = ip_address(request.META.get("REMOTE_ADDR", ""))
    except ValueError as error:
        raise LoginThrottleUnavailable from error
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return salted_hmac("platform_security.login_throttle", address.compressed, algorithm="sha256").hexdigest()


def prune_expired_windows(now):
    expired = list(
        LoginAttemptWindow.objects.select_for_update(skip_locked=True)
        .filter(expires_at__lte=now).order_by("expires_at").values_list("pk", flat=True)[:32]
    )
    LoginAttemptWindow.objects.filter(pk__in=expired).delete()


def authenticate_with_throttle(request, username, password):
    try:
        with transaction.atomic():
            return _authenticate_with_throttle(request, username, password)
    except (InterfaceError, OperationalError) as error:
        raise LoginThrottleUnavailable from error
    except ProgrammingError as error:
        # A database that has not received the required migration may lack a table.
        if getattr(error.__cause__, "sqlstate", None) != "42P01":
            raise
        raise LoginThrottleUnavailable from error


def _authenticate_with_throttle(request, username, password):
    if connection.vendor != "postgresql":
        raise LoginThrottleUnavailable
    key = client_key(request)
    # Serialize the check, password verification and failure update across workers.
    lock_id = int.from_bytes(bytes.fromhex(key[:16]), byteorder="big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [lock_id])
        if not cursor.fetchone()[0]:
            raise LoginThrottleUnavailable

    window = LoginAttemptWindow.objects.select_for_update(nowait=True).filter(pk=key).first()
    now = timezone.now()
    active = window is not None and window.expires_at > now
    if active and window.failures >= settings.LOGIN_FAILURE_LIMIT:
        raise LoginThrottled(ceil((window.expires_at - now).total_seconds()))

    user = auth.authenticate(request, username=username, password=password)
    if user is not None and user.is_active:
        return user

    if active:
        window.failures += 1
        window.save(update_fields=["failures"])
    else:
        LoginAttemptWindow.objects.update_or_create(
            client_key=key,
            defaults={
                "failures": 1,
                "expires_at": now + timedelta(seconds=settings.LOGIN_FAILURE_WINDOW_SECONDS),
            },
        )
    prune_expired_windows(now)
    return None
