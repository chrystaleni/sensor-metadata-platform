import pytest
from django.conf import settings
from django.db import connection


@pytest.mark.django_db
@pytest.mark.postgis
def test_database_uses_postgis_and_extension_is_available():
    assert (
        settings.DATABASES["default"]["ENGINE"]
        == "django.contrib.gis.db.backends.postgis"
    )
    assert connection.vendor == "postgresql"

    with connection.cursor() as cursor:
        cursor.execute("SELECT PostGIS_Version();")
        postgis_version = cursor.fetchone()[0]

    assert postgis_version
