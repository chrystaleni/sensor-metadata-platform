"""Authentication events reach the application log (Phase 2, scenario S4), never with passwords."""

import logging
from contextlib import contextmanager

import pytest
from django.contrib.auth import get_user_model

from .test_session import PASSWORD, bootstrap, browser, login, user  # noqa: F401  (fixtures)

pytestmark = pytest.mark.django_db


@contextmanager
def auth_log():
    """Collect the messages written to the authentication logger."""
    records = []
    handler = logging.Handler(level=logging.INFO)
    handler.emit = lambda record: records.append(record.getMessage())
    logger = logging.getLogger("platform_security.auth")
    previous = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


def test_failed_login_is_logged_without_the_password(browser, user):
    token = bootstrap(browser)
    with auth_log() as lines:
        assert login(browser, token, password="wrong-password-123").status_code == 400
    assert lines == ["Failed login for username='member' from 127.0.0.1"]
    assert not any("wrong-password-123" in line for line in lines)


def test_deactivated_account_and_unknown_user_are_logged_as_failed(browser, user):
    get_user_model().objects.filter(pk=user.pk).update(is_active=False)
    token = bootstrap(browser)
    with auth_log() as lines:
        login(browser, token)
        login(browser, token, username="nobody\nINJECTED")
    assert lines[0] == "Failed login for username='member' from 127.0.0.1"
    assert "\n" not in lines[1] and "nobody?INJECTED" in lines[1]
    assert not any(PASSWORD in line for line in lines)


def test_successful_login_and_logout_are_logged(browser, user):
    token = bootstrap(browser)
    with auth_log() as lines:
        assert login(browser, token).status_code == 200
        token = bootstrap(browser)
        assert browser.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code == 200
    assert lines == [f"Login of user {user.pk} from 127.0.0.1", f"Logout of user {user.pk}"]
