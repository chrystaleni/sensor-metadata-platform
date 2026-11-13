from django.apps import apps
from django.conf import settings
from django.db import connection
from rest_framework.exceptions import PermissionDenied


def lock_metadata_write(department_id, *, controlled_list=False):
    """Lock inside the write transaction before reading the data to be changed."""
    # Ordinary writes can share the list lock. List edits need exclusive access
    # so a validation check and a concurrent list deletion cannot race.
    operation = "pg_advisory_xact_lock" if controlled_list else "pg_advisory_xact_lock_shared"
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {operation}(%s, %s)", [317, 1])

    department = apps.get_model(settings.METADATA_DEPARTMENT_MODEL)
    if not department.objects.select_for_update(no_key=True).filter(pk=department_id).exists():
        raise PermissionDenied("This department is unavailable.")
