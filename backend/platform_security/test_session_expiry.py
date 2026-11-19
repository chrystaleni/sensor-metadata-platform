from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest
from django.conf import settings as django_settings
from django.contrib.sessions.models import Session
from django.db import OperationalError, connection, connections, transaction
from django.test import Client

from local_departments.models import Department, Organisation
from metadata.models import PhysicalDevice, PhysicalDeviceType
from metadata.views import PhysicalDeviceViewSet

from . import session_expiry
from .models import UserDepartment, UserRole
from .test_session import ANONYMOUS, AUTH, bootstrap, browser, login, user


pytestmark = pytest.mark.django_db
DEVICES = "/api/v1/physical-devices/"
LIFETIME = session_expiry.SESSION_LIFETIME
START = datetime(2030, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def clock(monkeypatch):
    now = START

    def set_elapsed(seconds):
        nonlocal now
        now = START + timedelta(seconds=seconds)

    monkeypatch.setattr(session_expiry.timezone, "now", lambda: now)
    return set_elapsed


@pytest.fixture
def signed_in(clock, browser, user):
    assert login(browser, bootstrap(browser)).status_code == 200
    return browser


@pytest.fixture
def device_payload(settings, user):
    settings.METADATA_ACCESS_POLICY = "platform_security.access.DepartmentAccessPolicy"
    platform, _ = Organisation.objects.get_or_create(code="platform", defaults={"name": "Platform"})
    owner = Department.objects.create(organisation=platform, name="Platform")
    org = Organisation.objects.create(code="demo", name="Demo")
    department = Department.objects.create(organisation=org, name="North")
    settings.METADATA_PLATFORM_DEPARTMENT_ID = owner.pk
    device_type = PhysicalDeviceType.objects.create(department=owner, name="Weather station")
    UserRole.objects.create(user=user, role=UserRole.Role.EDITOR)
    UserDepartment.objects.create(user=user, department=department)
    return {"department": department.pk, "device_type": device_type.pk, "name": "Station"}


def token(browser):
    return browser.cookies[django_settings.CSRF_COOKIE_NAME].value


def key(browser):
    return browser.cookies[django_settings.SESSION_COOKIE_NAME].value


def status(browser):
    return browser.get(f"{AUTH}session/").json()


def create_device(browser, payload, **headers):
    return browser.post(DEVICES, payload, content_type="application/json", **headers)


def test_login_sets_utc_lifetime_and_database_absolute_expiration(signed_in):
    absolute = START + timedelta(hours=8)
    assert signed_in.session[LIFETIME] == [START.isoformat(), START.isoformat(), absolute.isoformat()]
    assert Session.objects.get(pk=key(signed_in)).expire_date == absolute


def test_idle_boundary_invalidates_session_before_protected_view(signed_in, clock, device_payload):
    old_key = key(signed_in)
    clock(1799)
    assert signed_in.get(DEVICES).status_code == 200
    clock(1800)
    assert create_device(signed_in, device_payload, HTTP_X_CSRFTOKEN=token(signed_in)).status_code == 403
    assert not PhysicalDevice.objects.exists()
    assert not Session.objects.filter(pk=old_key).exists()
    assert status(signed_in) == ANONYMOUS


def test_successful_writes_renew_idle_lifetime_without_moving_absolute_boundary(signed_in, clock, device_payload):
    initial = signed_in.session[LIFETIME]
    for elapsed in range(1799, 28800, 1799):
        clock(elapsed)
        response = create_device(
            signed_in, {**device_payload, "name": f"Station {elapsed}"},
            HTTP_X_CSRFTOKEN=token(signed_in),
        )
        assert response.status_code == 201
        assert signed_in.session[LIFETIME] == [
            initial[0], (START + timedelta(seconds=elapsed)).isoformat(), initial[2],
        ]
    clock(28799)
    assert status(signed_in)["authenticated"]
    clock(28800)
    assert status(signed_in) == ANONYMOUS


def test_successful_write_resets_idle_deadline(signed_in, clock, device_payload):
    clock(1000)
    assert create_device(signed_in, device_payload, HTTP_X_CSRFTOKEN=token(signed_in)).status_code == 201
    clock(2799)
    assert status(signed_in)["authenticated"]
    clock(2800)
    assert status(signed_in) == ANONYMOUS


def test_shorter_configured_timeouts_apply_to_new_sessions(settings, clock, browser, user, device_payload):
    settings.SESSION_IDLE_TIMEOUT_SECONDS = 10
    settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS = 15
    assert login(browser, bootstrap(browser)).status_code == 200
    clock(9)
    assert create_device(browser, device_payload, HTTP_X_CSRFTOKEN=token(browser)).status_code == 201
    clock(14)
    assert status(browser)["authenticated"]
    clock(15)
    assert status(browser) == ANONYMOUS


@pytest.mark.parametrize("path", [f"{AUTH}session/", f"{AUTH}csrf/", DEVICES])
def test_reads_do_not_renew_activity(signed_in, clock, device_payload, path):
    initial = signed_in.session[LIFETIME]
    clock(1799)
    assert signed_in.get(path).status_code == 200
    assert signed_in.session[LIFETIME] == initial
    clock(1800)
    assert status(signed_in) == ANONYMOUS


def test_browser_restoration_preserves_original_lifetime(signed_in, clock):
    initial = signed_in.session[LIFETIME]
    restored = Client(enforce_csrf_checks=True)
    restored.cookies[django_settings.SESSION_COOKIE_NAME] = key(signed_in)
    clock(1000)
    assert status(restored)["authenticated"]
    assert restored.session[LIFETIME] == initial
    clock(1800)
    assert status(restored) == ANONYMOUS


def test_explicit_logout_deletes_session(signed_in):
    old_key = key(signed_in)
    response = signed_in.post(f"{AUTH}logout/", HTTP_X_CSRFTOKEN=token(signed_in))
    assert response.json() == ANONYMOUS
    assert not Session.objects.filter(pk=old_key).exists()


def test_failed_and_throttled_login_do_not_renew_session(signed_in, clock):
    initial = signed_in.session[LIFETIME]
    clock(1799)
    for _ in range(5):
        assert login(signed_in, token(signed_in), password="wrong").status_code == 400
    assert login(signed_in, token(signed_in)).status_code == 429
    assert signed_in.session[LIFETIME] == initial
    clock(1800)
    assert status(signed_in) == ANONYMOUS


@pytest.mark.parametrize("state", [
    None,
    ["invalid", "invalid", "invalid"],
    ["2030-01-01T00:00:00"] * 3,
    ["2029-12-31T23:59:00+00:00", "2030-01-01T00:01:00+00:00", "2030-01-01T08:00:00+00:00"],
    [None, [], {}],
])
def test_missing_or_invalid_lifetime_is_rejected(signed_in, state):
    old_key = key(signed_in)
    session = signed_in.session
    if state is None:
        del session[LIFETIME]
    else:
        session[LIFETIME] = state
    session.save()
    assert status(signed_in) == ANONYMOUS
    assert not Session.objects.filter(pk=old_key).exists()


def test_tampered_session_payload_is_rejected(signed_in):
    old_key = key(signed_in)
    row = Session.objects.get(pk=old_key)
    Session.objects.filter(pk=old_key).update(session_data=f"{row.session_data}tampered")
    assert status(signed_in) == ANONYMOUS


def test_anonymous_client_cannot_supply_timeout_state(browser, device_payload, clock):
    assert status(browser) == ANONYMOUS
    assert create_device(browser, {LIFETIME: [START.isoformat()] * 3}).status_code == 403
    assert django_settings.SESSION_COOKIE_NAME not in browser.cookies
    response = login(browser, bootstrap(browser), **{LIFETIME: [START.isoformat()] * 3})
    assert response.status_code == 400
    assert django_settings.SESSION_COOKIE_NAME not in browser.cookies


def test_csrf_is_required_and_rejected_write_does_not_renew(signed_in, clock, device_payload):
    initial = signed_in.session[LIFETIME]
    clock(1799)
    assert create_device(signed_in, device_payload).status_code == 403
    assert signed_in.session[LIFETIME] == initial
    clock(1800)
    assert login(signed_in).status_code == 403
    assert status(signed_in) == ANONYMOUS


def test_relogin_rotates_session_and_csrf_and_preserves_assignments(signed_in, clock, user, device_payload):
    old_key, old_token = key(signed_in), token(signed_in)
    existing_roles = list(UserRole.objects.filter(user=user).values())
    existing_memberships = list(UserDepartment.objects.filter(user=user).values())
    clock(1000)
    assert login(signed_in, old_token).status_code == 200
    assert key(signed_in) != old_key
    assert token(signed_in) != old_token
    assert not Session.objects.filter(pk=old_key).exists()
    assert signed_in.session[LIFETIME][0] == (START + timedelta(seconds=1000)).isoformat()
    assert list(UserRole.objects.filter(user=user).values()) == existing_roles
    assert list(UserDepartment.objects.filter(user=user).values()) == existing_memberships
    clock(1800)
    assert status(signed_in)["authenticated"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("invalidate_in_parallel", [False, True])
def test_in_flight_request_cannot_renew_at_idle_boundary(
    signed_in, clock, device_payload, monkeypatch, invalidate_in_parallel,
):
    old_key, csrf_token = key(signed_in), token(signed_in)
    entered, resume = Event(), Event()
    renew = session_expiry.renew_activity

    def paused_renew(session_key):
        entered.set()
        assert resume.wait(timeout=10)
        renew(session_key)

    def in_flight_write():
        worker = Client(enforce_csrf_checks=True)
        worker.cookies[django_settings.SESSION_COOKIE_NAME] = old_key
        worker.cookies[django_settings.CSRF_COOKIE_NAME] = csrf_token
        try:
            return create_device(worker, device_payload, HTTP_X_CSRFTOKEN=csrf_token).status_code
        finally:
            connections.close_all()

    monkeypatch.setattr(session_expiry, "renew_activity", paused_renew)
    clock(1799)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(in_flight_write)
        try:
            assert entered.wait(timeout=10)
            clock(1800)
            if invalidate_in_parallel:
                assert status(signed_in) == ANONYMOUS
        finally:
            resume.set()
        assert pending.result(timeout=10) == 201
    assert status(signed_in) == ANONYMOUS
    assert not Session.objects.filter(pk=old_key).exists()


@pytest.mark.django_db(transaction=True)
def test_committed_write_keeps_success_when_renewal_rolls_back(
    signed_in, clock, device_payload, monkeypatch, caplog,
):
    initial = signed_in.session[LIFETIME]
    old_key = key(signed_in)
    original_save = Session.save

    def fail_after_renewal_write(row, *args, **kwargs):
        if kwargs.get("update_fields") != ["session_data"]:
            return original_save(row, *args, **kwargs)

        # Other connections can already see the metadata write.
        observer = connection.copy()
        try:
            with observer.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM metadata_physicaldevice WHERE name = %s",
                    [device_payload["name"]],
                )
                assert cursor.fetchone() == (1,)
        finally:
            observer.close()

        original_save(row, *args, **kwargs)
        raise OperationalError("sensitive diagnostic for test")

    monkeypatch.setattr(Session, "save", fail_after_renewal_write)
    clock(1000)
    response = create_device(signed_in, device_payload, HTTP_X_CSRFTOKEN=token(signed_in))
    assert response.status_code == 201
    assert PhysicalDevice.objects.get().pk == response.json()["id"]
    assert key(signed_in) == old_key
    assert signed_in.session[LIFETIME] == initial
    assert "Session inactivity renewal failed" in caplog.text
    assert "sensitive diagnostic for test" not in caplog.text


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("expired", [True, False], ids=["pre-view", "post-view"])
def test_contended_session_lock_is_bounded(
    signed_in, clock, device_payload, monkeypatch, caplog, expired,
):
    old_key, csrf_token = key(signed_in), token(signed_in)
    initial = signed_in.session[LIFETIME]
    clock(1800 if expired else 1000)
    if expired:
        def unexpected_dispatch(*args, **kwargs):
            pytest.fail("The protected view ran before session expiry could be verified.")

        monkeypatch.setattr(PhysicalDeviceViewSet, "dispatch", unexpected_dispatch)

    def competing_write():
        worker = Client(enforce_csrf_checks=True)
        worker.cookies[django_settings.SESSION_COOKIE_NAME] = old_key
        worker.cookies[django_settings.CSRF_COOKIE_NAME] = csrf_token
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '4s'")

            response = create_device(worker, device_payload, HTTP_X_CSRFTOKEN=csrf_token)

            with connection.cursor() as cursor:
                cursor.execute("SHOW lock_timeout")
                assert cursor.fetchone() == ("4s",)
            return response
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction.atomic():
            Session.objects.select_for_update().get(pk=old_key)
            pending = executor.submit(competing_write)
            response = pending.result(timeout=3)

    assert signed_in.session[LIFETIME] == initial
    if expired:
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "1"
        assert response.json() == {"detail": "Session verification is temporarily unavailable."}
        assert not PhysicalDevice.objects.exists()
        assert "Session expiry verification is temporarily unavailable." in caplog.text
        assert status(signed_in) == ANONYMOUS
    else:
        assert response.status_code == 201
        assert PhysicalDevice.objects.get().pk == response.json()["id"]
        assert "Session inactivity renewal failed" in caplog.text


def test_successful_renewal_restores_enclosing_transaction_lock_timeout(
    signed_in, clock, device_payload, monkeypatch,
):
    lock_session = session_expiry.locked_session

    def check_scoped_timeout(session_key):
        with connection.cursor() as cursor:
            cursor.execute("SHOW lock_timeout")
            assert cursor.fetchone() == ("250ms",)
        return lock_session(session_key)

    monkeypatch.setattr(session_expiry, "locked_session", check_scoped_timeout)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '4s'")

        clock(1000)
        response = create_device(signed_in, device_payload, HTTP_X_CSRFTOKEN=token(signed_in))
        assert response.status_code == 201

        with connection.cursor() as cursor:
            cursor.execute("SHOW lock_timeout")
            assert cursor.fetchone() == ("4s",)
