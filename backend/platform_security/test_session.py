import pytest
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.test import Client

from local_departments.models import Department, Organisation
from metadata.access import NoAccessPolicy, get_access_policy
from metadata.models import PhysicalDevice, PhysicalDeviceType

from .models import UserDepartment, UserRole


pytestmark = pytest.mark.django_db
AUTH = "/api/v1/auth/"
PASSWORD = "local-test-password"
ANONYMOUS = {"authenticated": False, "user": None}


@pytest.fixture
def browser():
    return Client(enforce_csrf_checks=True)


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="member", password=PASSWORD)


def bootstrap(browser):
    response = browser.get(f"{AUTH}csrf/")
    assert response.status_code == 200
    return browser.cookies[django_settings.CSRF_COOKIE_NAME].value


def login(browser, token=None, **overrides):
    headers = {} if token is None else {"HTTP_X_CSRFTOKEN": token}
    return browser.post(
        f"{AUTH}login/",
        {"username": "member", "password": PASSWORD, **overrides},
        content_type="application/json",
        **headers,
    )


def test_anonymous_session_and_csrf_bootstrap(browser):
    response = browser.get(f"{AUTH}session/")
    assert response.json() == ANONYMOUS
    assert "no-store" in response.headers["Cache-Control"]

    response = browser.get(f"{AUTH}csrf/")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert django_settings.CSRF_COOKIE_NAME in response.cookies
    assert django_settings.SESSION_COOKIE_NAME not in browser.cookies


@pytest.mark.parametrize("token", [None, "invalid"])
def test_anonymous_login_requires_valid_csrf(browser, user, token):
    bootstrap(browser)
    assert login(browser, token).status_code == 403
    assert browser.get(f"{AUTH}session/").json() == ANONYMOUS


def test_login_rotates_csrf_and_restores_session_on_another_client(browser, user):
    original_token = bootstrap(browser)
    original_session = browser.session
    original_session["prelogin"] = True
    original_session.save()
    old_key = original_session.session_key
    response = login(browser, original_token)

    expected = {"authenticated": True, "user": {"id": user.pk, "username": user.username}}
    assert response.status_code == 200
    assert response.json() == expected
    assert "no-store" in response.headers["Cache-Control"]
    assert browser.cookies[django_settings.CSRF_COOKIE_NAME].value != original_token
    assert browser.cookies[django_settings.SESSION_COOKIE_NAME].value != old_key

    restored = Client(enforce_csrf_checks=True)
    restored.cookies[django_settings.SESSION_COOKIE_NAME] = browser.cookies[django_settings.SESSION_COOKIE_NAME].value
    assert restored.get(f"{AUTH}session/").json() == expected
    unauthenticated = Client()
    unauthenticated.cookies[django_settings.SESSION_COOKIE_NAME] = old_key
    assert unauthenticated.get(f"{AUTH}session/").json() == ANONYMOUS


@pytest.mark.parametrize(("username", "password", "active"), [
    ("member", "wrong-password", True),
    ("unknown", PASSWORD, True),
    ("member", PASSWORD, False),
])
def test_credentials_fail_with_same_error(browser, user, username, password, active):
    user.is_active = active
    user.save(update_fields=["is_active"])

    response = login(browser, bootstrap(browser), username=username, password=password)
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid username or password."}
    assert browser.get(f"{AUTH}session/").json() == ANONYMOUS


def test_logout_requires_authenticated_post_and_current_csrf(browser, user):
    old_token = bootstrap(browser)
    assert browser.post(f"{AUTH}logout/", HTTP_X_CSRFTOKEN=old_token).status_code == 403
    assert login(browser, old_token).status_code == 200
    session_key = browser.cookies[django_settings.SESSION_COOKIE_NAME].value

    assert browser.get(f"{AUTH}logout/").status_code == 405
    assert browser.post(f"{AUTH}logout/").status_code == 403
    assert browser.post(f"{AUTH}logout/", HTTP_X_CSRFTOKEN=old_token).status_code == 403
    assert browser.get(f"{AUTH}session/").json()["authenticated"] is True

    current_token = browser.cookies[django_settings.CSRF_COOKIE_NAME].value
    response = browser.post(f"{AUTH}logout/", HTTP_X_CSRFTOKEN=current_token)
    assert response.status_code == 200
    assert response.json() == ANONYMOUS
    browser.cookies[django_settings.SESSION_COOKIE_NAME] = session_key
    assert browser.get(f"{AUTH}session/").json() == ANONYMOUS


def test_login_rejects_privilege_fields_and_preserves_existing_assignments(browser, user):
    organisation = Organisation.objects.create(code="demo", name="Demo")
    department = Department.objects.create(organisation=organisation, name="North")
    membership = UserDepartment.objects.create(user=user, department=department)
    role = UserRole.objects.create(user=user, role=UserRole.Role.VIEWER)
    token = bootstrap(browser)

    response = login(browser, token, role="SYSTEM_ADMIN", department=department.pk, is_superuser=True)
    assert response.status_code == 400
    assert browser.get(f"{AUTH}session/").json() == ANONYMOUS
    assert login(browser, token).status_code == 200
    assert list(UserRole.objects.values_list("pk", "user_id", "role")) == [
        (role.pk, user.pk, UserRole.Role.VIEWER),
    ]
    assert list(UserDepartment.objects.values_list("pk", "user_id", "department_id")) == [
        (membership.pk, user.pk, department.pk),
    ]
    user.refresh_from_db()
    assert not user.is_superuser


def test_roleless_user_can_sign_in_without_creating_assignments_or_gaining_metadata_access(browser, user):
    organisation = Organisation.objects.create(code="demo", name="Demo")
    department = Department.objects.create(organisation=organisation, name="North")
    device_type = PhysicalDeviceType.objects.create(department=department, name="Test type")
    device = PhysicalDevice.objects.create(department=department, name="Hidden device", device_type=device_type)
    assert isinstance(get_access_policy(), NoAccessPolicy)

    assert login(browser, bootstrap(browser)).status_code == 200
    assert not UserRole.objects.filter(user=user).exists()
    assert not UserDepartment.objects.filter(user=user).exists()

    url = "/api/v1/physical-devices/"
    assert browser.get(url).json()["count"] == 0
    assert browser.get(f"{url}{device.pk}/").status_code == 404
    token = browser.cookies[django_settings.CSRF_COOKIE_NAME].value
    assert browser.post(url, {
        "department": department.pk, "name": "Blocked", "device_type": device_type.pk,
    }, content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code == 403
