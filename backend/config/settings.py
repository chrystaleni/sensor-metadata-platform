"""Django settings for local development."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPOSITORY_ROOT / ".env", override=False)

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-development-only-change-me",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "True").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

DATABASE_ENGINE = os.environ.get("DJANGO_DATABASE_ENGINE", "postgis").strip().lower()
USE_POSTGIS = DATABASE_ENGINE in {"postgis", "postgres", "postgresql"}
if DATABASE_ENGINE not in {"sqlite", "postgis", "postgres", "postgresql"}:
    raise ImproperlyConfigured(
        "DJANGO_DATABASE_ENGINE must be either 'sqlite' or 'postgis'."
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "local_departments",
    "metadata",
    "platform_security",
]

if USE_POSTGIS:
    INSTALLED_APPS.insert(0, "django.contrib.gis")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "platform_security.session_expiry.SessionExpiryMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if DATABASE_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "db.sqlite3",
        }
    }
elif DATABASE_ENGINE in {"postgis", "postgres", "postgresql"}:
    required_database_vars = (
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
    )
    missing_database_vars = [
        name for name in required_database_vars if not os.environ.get(name)
    ]
    if missing_database_vars:
        missing = ", ".join(missing_database_vars)
        raise ImproperlyConfigured(
            f"{missing} must be set when DJANGO_DATABASE_ENGINE=postgis."
        )

    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ["POSTGRES_USER"],
            "PASSWORD": os.environ["POSTGRES_PASSWORD"],
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ["POSTGRES_PORT"],
            "TEST": {"TEMPLATE": "template_postgis"},
        }
    }

AUTH_PASSWORD_VALIDATORS = []

try:
    LOGIN_FAILURE_LIMIT = int(os.environ.get("LOGIN_FAILURE_LIMIT", "5"))
    LOGIN_FAILURE_WINDOW_SECONDS = int(os.environ.get("LOGIN_FAILURE_WINDOW_SECONDS", "900"))
except ValueError as error:
    raise ImproperlyConfigured("Login throttling settings must be integers.") from error
if not 0 < LOGIN_FAILURE_LIMIT <= 2**31 - 1 or not 0 < LOGIN_FAILURE_WINDOW_SECONDS <= 2**31 - 1:
    raise ImproperlyConfigured("Login throttling settings must be positive 32-bit integers.")

try:
    SESSION_IDLE_TIMEOUT_SECONDS = int(os.environ.get("SESSION_IDLE_TIMEOUT_SECONDS", "1800"))
    SESSION_ABSOLUTE_TIMEOUT_SECONDS = int(os.environ.get("SESSION_ABSOLUTE_TIMEOUT_SECONDS", "28800"))
except ValueError as error:
    raise ImproperlyConfigured("Session timeout settings must be integers.") from error
if not 0 < SESSION_IDLE_TIMEOUT_SECONDS <= SESSION_ABSOLUTE_TIMEOUT_SECONDS:
    raise ImproperlyConfigured("Session timeouts require 0 < idle timeout <= absolute timeout.")
if SESSION_ABSOLUTE_TIMEOUT_SECONDS > 2**31 - 1:
    raise ImproperlyConfigured("The absolute session timeout must fit in a positive 32-bit integer.")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Department and access adapters are supplied by the shared security layer.
METADATA_DEPARTMENT_MODEL = os.environ.get("METADATA_DEPARTMENT_MODEL", "local_departments.Department")
# An unset or invalid ID leaves shared catalogs unavailable.
try:
    _platform_department_id = int(os.environ.get("METADATA_PLATFORM_DEPARTMENT_ID", ""))
except ValueError:
    _platform_department_id = 0
METADATA_PLATFORM_DEPARTMENT_ID = (
    _platform_department_id if 0 < _platform_department_id < 2**63 else None
)
METADATA_ACCESS_POLICY = os.environ.get("METADATA_ACCESS_POLICY", "metadata.access.NoAccessPolicy")
GDAL_LIBRARY_PATH = os.environ.get("GDAL_LIBRARY_PATH")
GEOS_LIBRARY_PATH = os.environ.get("GEOS_LIBRARY_PATH")

REST_FRAMEWORK = {
    "DEFAULT_PARSER_CLASSES": [
        "core.parsers.SafeJSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
