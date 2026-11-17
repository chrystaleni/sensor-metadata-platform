"""Reproduce the original 0004 upgrade failure in pytest's disposable database.

A future replacement path must preserve cross-Department duplicate pairs and
install Department-scoped uniqueness. This test deliberately keeps exercising
the original migration graph and its atomic failure.
"""

import pytest
from django.conf import settings
from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder


BASELINE = ("metadata", "0003_externalidentifier_created_by_and_more")
GLOBAL_UNIQUENESS = ("metadata", "0004_identifier_system_uniqueness")
TARGET = ("metadata", "0005_identifier_department_scope")
INDEX_NAME = "meta_active_external_identifier"


def original_executor():
    executor = MigrationExecutor(connection)
    executor.loader = MigrationLoader(connection, replace_migrations=False)
    return executor


def identifier_index():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pg_get_indexdef(indexrelid), indisunique, indisvalid
            FROM pg_index
            WHERE indrelid = 'metadata_externalidentifier'::regclass
              AND indexrelid = to_regclass(%s)
            """,
            [INDEX_NAME],
        )
        return cursor.fetchone()


@pytest.mark.postgis
@pytest.mark.django_db(transaction=True)
def test_original_0004_rejects_cross_department_pairs_atomically():
    assert connection.vendor == "postgresql"
    executor = original_executor()
    original_targets = executor.loader.graph.leaf_nodes()
    identifiers = None
    fixture_ids = []
    try:
        executor.migrate([BASELINE])
        historical_apps = original_executor().loader.project_state([BASELINE]).apps
        department_app, department_name = settings.METADATA_DEPARTMENT_MODEL.split(".")
        Department = historical_apps.get_model(department_app, department_name)
        NetworkElementType = historical_apps.get_model("metadata", "NetworkElementType")
        NetworkElement = historical_apps.get_model("metadata", "NetworkElement")
        identifiers = historical_apps.get_model("metadata", "ExternalIdentifier")

        north = Department.objects.create(name="Upgrade North")
        south = Department.objects.create(name="Upgrade South")
        element_type = NetworkElementType.objects.create(department=north, name="Upgrade site")
        for department in (north, south):
            parent = NetworkElement.objects.create(
                department=department, element_type=element_type, name=department.name,
            )
            identifier = identifiers.objects.create(
                network_element=parent, source="ERP", value="shared-upgrade-pair",
            )
            fixture_ids.append(identifier.pk)

        models = (Department, NetworkElementType, NetworkElement, identifiers)
        before_records = [list(model.objects.order_by("pk").values()) for model in models]
        before_history = list(MigrationRecorder.Migration.objects.order_by("pk").values())
        before_index = identifier_index()
        assert before_index is not None
        assert before_index[1:] == (True, True)
        assert "(network_element_id, source, value)" in before_index[0]
        assert "WHERE (deleted_at IS NULL)" in before_index[0]
        assert BASELINE in MigrationRecorder(connection).applied_migrations()
        assert GLOBAL_UNIQUENESS not in MigrationRecorder(connection).applied_migrations()
        assert TARGET not in MigrationRecorder(connection).applied_migrations()

        with pytest.raises(IntegrityError) as failure:
            original_executor().migrate([TARGET])

        assert failure.value.__cause__.sqlstate == "23505"
        assert failure.value.__cause__.diag.constraint_name == INDEX_NAME
        assert [list(model.objects.order_by("pk").values()) for model in models] == before_records
        assert list(MigrationRecorder.Migration.objects.order_by("pk").values()) == before_history
        assert identifier_index() == before_index
        assert identifiers.objects.filter(pk__in=fixture_ids, deleted_at__isnull=True).count() == 2
    finally:
        # Remove only this test's conflicting rows before restoring the schema.
        # Raw SQL also works if an unexpected successful upgrade added columns
        # that the historical model does not know about.
        try:
            if fixture_ids:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM metadata_externalidentifier WHERE id = ANY(%s)",
                        [fixture_ids],
                    )
        finally:
            original_executor().migrate(original_targets)
