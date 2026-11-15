import logging
from contextlib import contextmanager
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import auth
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import InterfaceError, OperationalError, connection, transaction
from django.http import JsonResponse
from django.utils import timezone


SESSION_LIFETIME = "platform_session_lifetime"
ACTIVITY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SESSION_ROW_LOCK_TIMEOUT = "250ms"
logger = logging.getLogger(__name__)


class SessionRowBusy(Exception):
    pass


def start_session_lifetime(sender, request, **kwargs):
    now = timezone.now()
    absolute = now + timedelta(seconds=settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS)
    request.session[SESSION_LIFETIME] = [now.isoformat(), now.isoformat(), absolute.isoformat()]
    request.session.set_expiry(absolute)


def session_deadline(state, now):
    if not isinstance(state, list) or len(state) != 3:
        return None
    try:
        started, activity, absolute = (datetime.fromisoformat(value) for value in state)
    except (TypeError, ValueError):
        return None
    if any(value.utcoffset() != timedelta(0) for value in (started, activity, absolute)):
        return None
    if not started <= activity <= now or activity >= absolute:
        return None
    return min(
        activity + timedelta(seconds=settings.SESSION_IDLE_TIMEOUT_SECONDS),
        absolute,
        started + timedelta(seconds=settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS),
    )


@contextmanager
def session_lock_transaction():
    with transaction.atomic():
        if connection.vendor != "postgresql":
            yield
            return

        with connection.cursor() as cursor:
            cursor.execute("SHOW lock_timeout")
            previous_timeout = cursor.fetchone()[0]
            cursor.execute("SELECT set_config('lock_timeout', %s, true)", [SESSION_ROW_LOCK_TIMEOUT])

        yield

        # A rollback restores the prior setting on error. Restore it explicitly
        # on success because an enclosing transaction can outlive this savepoint.
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('lock_timeout', %s, true)", [previous_timeout])


def locked_session(session_key):
    sessions = Session.objects.filter(session_key=session_key)
    skip_locked = connection.features.has_select_for_update_skip_locked
    row = sessions.select_for_update(skip_locked=skip_locked).first()
    if row is None and skip_locked and sessions.exists():
        # Skipping contention avoids a PostgreSQL error log containing the session key.
        raise SessionRowBusy
    return row


def read_lifetime(row, now):
    data = SessionStore().decode(row.session_data)
    deadline = session_deadline(data.get(SESSION_LIFETIME), now)
    return data if deadline is not None and now < min(deadline, row.expire_date) else None


@session_lock_transaction()
def invalidate_if_expired(request):
    # A concurrent request may have renewed the session since Django loaded it.
    row = locked_session(request.session.session_key)
    if row is None or read_lifetime(row, timezone.now()) is None:
        auth.logout(request)


@session_lock_transaction()
def renew_activity(session_key):
    # Lock only while renewing. An in-flight request must recheck the current
    # session after taking the lock, since it may have expired or been deleted.
    row = locked_session(session_key)
    if row is None:
        return

    now = timezone.now()
    data = read_lifetime(row, now)
    if data is None:
        return

    data[SESSION_LIFETIME][1] = now.isoformat()
    row.session_data = SessionStore().encode(data)
    row.save(update_fields=["session_data"])


class SessionExpiryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session_key = None
        try:
            if request.user.is_authenticated:
                now = timezone.now()
                deadline = session_deadline(request.session.get(SESSION_LIFETIME), now)
                if deadline is None or now >= deadline:
                    invalidate_if_expired(request)
                if request.user.is_authenticated:
                    session_key = request.session.session_key
        except (SessionRowBusy, InterfaceError, OperationalError):
            logger.warning("Session expiry verification is temporarily unavailable.")
            return JsonResponse(
                {"detail": "Session verification is temporarily unavailable."},
                status=503,
                headers={"Retry-After": "1", "Cache-Control": "no-store"},
            )

        response = self.get_response(request)
        if (
            session_key
            and request.session.session_key == session_key
            and request.method in ACTIVITY_METHODS
            and 200 <= response.status_code < 300
            and self.is_metadata_view(request)
        ):
            try:
                renew_activity(session_key)
            except (SessionRowBusy, InterfaceError, OperationalError):
                logger.warning("Session inactivity renewal failed after a successful metadata write.")
        return response

    @staticmethod
    def is_metadata_view(request):
        from metadata.views import DepartmentScope

        view = getattr(request.resolver_match, "func", None)
        view_class = getattr(view, "cls", None)
        return view_class is not None and issubclass(view_class, DepartmentScope)
