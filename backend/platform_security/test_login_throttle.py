from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections, transaction
from django.test import Client

from . import login_throttle
from .models import LoginAttemptWindow, UserDepartment, UserRole
from .test_session import ANONYMOUS, AUTH, PASSWORD, bootstrap, login


@pytest.fixture(autouse=True)
def limit(settings):
    settings.LOGIN_FAILURE_LIMIT = 2
    settings.LOGIN_FAILURE_WINDOW_SECONDS = 900


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="member", password=PASSWORD)


@pytest.fixture
def browser():
    return Client(enforce_csrf_checks=True, REMOTE_ADDR="192.0.2.10")


@pytest.mark.django_db
def test_client_failure_budget_is_shared_by_usernames_and_success_does_not_reset(browser, user):
    token = bootstrap(browser)
    failure = {"detail": "Invalid username or password."}
    wrong = login(browser, token, password="wrong")
    assert (wrong.status_code, wrong.json()) == (400, failure)

    assert login(browser, token).status_code == 200
    assert not UserRole.objects.exists()
    assert not UserDepartment.objects.exists()
    token = browser.cookies[django_settings.CSRF_COOKIE_NAME].value
    unknown = login(browser, token, username="unknown")
    assert (unknown.status_code, unknown.json()) == (400, failure)
    blocked = login(browser, token)
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Too many login attempts. Try again later."}
    assert 1 <= int(blocked.headers["Retry-After"]) <= 900
    assert browser.get(f"{AUTH}session/").json()["authenticated"]
    assert LoginAttemptWindow.objects.get().failures == 2


@pytest.mark.django_db
@pytest.mark.parametrize(("username", "password", "active"), [
    ("member", "wrong", True),
    ("unknown", PASSWORD, True),
    ("member", PASSWORD, False),
])
def test_invalid_credentials_have_the_same_limit(browser, user, settings, username, password, active):
    settings.LOGIN_FAILURE_LIMIT = 1
    user.is_active = active
    user.save(update_fields=["is_active"])
    token = bootstrap(browser)
    response = login(browser, token, username=username, password=password)
    assert (response.status_code, response.json()) == (400, {"detail": "Invalid username or password."})
    assert login(browser, token, username=username, password=password).status_code == 429


@pytest.mark.django_db
def test_window_expires_and_expired_records_are_pruned(browser, settings, monkeypatch):
    settings.LOGIN_FAILURE_LIMIT = 1
    now = datetime(2026, 11, 15, tzinfo=UTC)
    monkeypatch.setattr(login_throttle.timezone, "now", lambda: now)
    monkeypatch.setattr(login_throttle.auth, "authenticate", lambda *args, **kwargs: None)
    LoginAttemptWindow.objects.create(client_key="expired", failures=1, expires_at=now)
    token = bootstrap(browser)
    assert login(browser, token).status_code == 400
    assert not LoginAttemptWindow.objects.filter(pk="expired").exists()

    now += timedelta(seconds=899)
    blocked = login(browser, token)
    assert (blocked.status_code, blocked.headers["Retry-After"]) == (429, "1")
    now += timedelta(seconds=1)
    assert login(browser, token).status_code == 400
    assert LoginAttemptWindow.objects.get().expires_at == now + timedelta(seconds=900)


@pytest.mark.django_db
def test_csrf_is_checked_first_and_forwarded_headers_cannot_reset_budget(browser, settings, monkeypatch):
    settings.LOGIN_FAILURE_LIMIT = 1
    monkeypatch.setattr(login_throttle.auth, "authenticate", lambda *args, **kwargs: None)
    token = bootstrap(browser)
    assert login(browser).status_code == 403
    assert not LoginAttemptWindow.objects.exists()
    assert login(browser, token).status_code == 400
    assert login(browser).status_code == 403

    response = browser.post(
        f"{AUTH}login/", {"username": "other", "password": PASSWORD}, content_type="application/json",
        HTTP_X_CSRFTOKEN=token, HTTP_X_FORWARDED_FOR="198.51.100.20",
    )
    assert response.status_code == 429
    assert LoginAttemptWindow.objects.count() == 1
    independent = Client(enforce_csrf_checks=True, REMOTE_ADDR="198.51.100.20")
    assert login(independent, bootstrap(independent)).status_code == 400
    assert LoginAttemptWindow.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_share_one_budget(monkeypatch):
    start = Barrier(4, timeout=10)
    monkeypatch.setattr(login_throttle.auth, "authenticate", lambda *args, **kwargs: None)

    def attempt():
        close_old_connections()
        try:
            client = Client(enforce_csrf_checks=True, REMOTE_ADDR="192.0.2.20")
            token = bootstrap(client)
            start.wait()
            return login(client, token).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(lambda _: attempt(), range(4)))
    assert set(statuses) <= {400, 429, 503}
    failures = statuses.count(400)
    assert 1 <= failures <= 2
    assert LoginAttemptWindow.objects.get().failures == failures

    client = Client(enforce_csrf_checks=True, REMOTE_ADDR="192.0.2.20")
    token = bootstrap(client)
    for _ in range(2 - failures):
        assert login(client, token).status_code == 400
    assert login(client, token).status_code == 429
    assert LoginAttemptWindow.objects.get().failures == 2


@pytest.mark.django_db(transaction=True)
def test_busy_advisory_lock_returns_without_waiting_or_authenticating(monkeypatch):
    address = "192.0.2.30"
    key = login_throttle.client_key(SimpleNamespace(META={"REMOTE_ADDR": address}))
    lock_id = int.from_bytes(bytes.fromhex(key[:16]), byteorder="big", signed=True)
    authenticate = Mock(return_value=None)
    monkeypatch.setattr(login_throttle.auth, "authenticate", authenticate)
    expires_at = login_throttle.timezone.now() + timedelta(seconds=900)
    window = LoginAttemptWindow.objects.create(client_key=key, failures=1, expires_at=expires_at)

    def competing_login():
        try:
            client = Client(enforce_csrf_checks=True, REMOTE_ADDR=address)
            response = login(client, bootstrap(client))
            return response, client.get(f"{AUTH}session/").json()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [lock_id])
                assert cursor.fetchone()[0]
            response, session = pool.submit(competing_login).result(timeout=5)

    assert response.status_code == 503
    assert response.json() == {"detail": "Login is temporarily unavailable."}
    assert response.headers["Retry-After"] == "1"
    assert session == ANONYMOUS
    assert django_settings.SESSION_COOKIE_NAME not in response.cookies
    authenticate.assert_not_called()
    window.refresh_from_db()
    assert (window.failures, window.expires_at) == (1, expires_at)


@pytest.mark.django_db
def test_database_failure_after_counter_write_rolls_back(browser, monkeypatch):
    monkeypatch.setattr(login_throttle.auth, "authenticate", lambda *args, **kwargs: None)

    def fail_cleanup(now):
        assert LoginAttemptWindow.objects.count() == 1
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM deliberately_missing_throttle_table")

    monkeypatch.setattr(login_throttle, "prune_expired_windows", fail_cleanup)
    response = login(browser, bootstrap(browser))

    assert response.status_code == 503
    assert response.json() == {"detail": "Login is temporarily unavailable."}
    assert response.headers["Retry-After"] == "1"
    assert django_settings.SESSION_COOKIE_NAME not in response.cookies
    assert browser.get(f"{AUTH}session/").json() == ANONYMOUS
    assert not LoginAttemptWindow.objects.exists()


@pytest.mark.django_db
def test_default_threshold_allows_five_failures(browser, settings, monkeypatch):
    settings.LOGIN_FAILURE_LIMIT = 5
    authenticate = Mock(return_value=None)
    monkeypatch.setattr(login_throttle.auth, "authenticate", authenticate)
    token = bootstrap(browser)
    for _ in range(5):
        response = login(browser, token)
        assert (response.status_code, response.json()) == (400, {"detail": "Invalid username or password."})
    blocked = login(browser, token)
    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["Retry-After"]) <= 900
    assert authenticate.call_count == 5
