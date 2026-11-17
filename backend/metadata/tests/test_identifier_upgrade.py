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


class OriginalMigrationLoader(MigrationLoader):
    """Exclude replacement files before constructing the historical graph."""

    def load_disk(self):
        super().load_disk()
        self.disk_migrations = {
            key: migration for key, migration in self.disk_migrations.items()
            if not migration.replaces
        }


class OriginalMigrationExecutor(MigrationExecutor):
    def __init__(self, database):
        self.connection = database
        self.loader = OriginalMigrationLoader(database, replace_migrations=False)
        self.recorder = MigrationRecorder(database)
        self.progress_callback = None
        applied = self.loader.applied_migrations
        replacement = ("metadata", "0004_squashed_0005_identifier_department_scope")
        if replacement in applied:
            # A completed replacement is schema-equivalent to both originals.
            for key in (GLOBAL_UNIQUENESS, TARGET):
                applied.setdefault(key, applied[replacement])
        self.loader.applied_migrations = {
            key: value for key, value in applied.items()
            if key in self.loader.graph.nodes
        }

    def unapply_migration(self, state, migration, fake=False):
        result = super().unapply_migration(state, migration, fake=fake)
        if (migration.app_label, migration.name) == TARGET:
            # Remove the completed-replacement marker only after the schema
            # operation succeeds. A failed reverse must retain its history.
            self.recorder.record_unapplied(
                "metadata", "0004_squashed_0005_identifier_department_scope",
            )
        return result


def original_executor():
    return OriginalMigrationExecutor(connection)


def restore_migrations():
    # Rebuild targets after transitions: partial application selects a different
    # graph from the fully applied replacement.
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
    with connection.cursor() as cursor:
        columns = {column.name for column in connection.introspection.get_table_description(
            cursor, "metadata_externalidentifier",
        )}
        constraints = connection.introspection.get_constraints(cursor, "metadata_externalidentifier")
    assert "department_id" in columns
    assert "meta_active_dept_external_identifier" in constraints
    assert "meta_identifier_element_department" in constraints


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
            restore_migrations()


REPLACEMENT = ("metadata", "0004_squashed_0005_identifier_department_scope")


@pytest.fixture
def historical_identifiers():
    executor = original_executor()
    recorder = MigrationRecorder(connection)
    original_history = set(recorder.applied_migrations())
    unrelated_history = list(
        recorder.migration_qs.exclude(app="metadata").order_by("pk").values()
    )
    ids = []
    try:
        executor.migrate([BASELINE])
        recorder.record_unapplied(*REPLACEMENT)
        assert REPLACEMENT not in recorder.applied_migrations()
        assert list(
            recorder.migration_qs.exclude(app="metadata").order_by("pk").values()
        ) == unrelated_history
        apps = original_executor().loader.project_state([BASELINE]).apps
        Department = apps.get_model(*settings.METADATA_DEPARTMENT_MODEL.split("."))
        Element = apps.get_model("metadata", "NetworkElement")
        Kind = apps.get_model("metadata", "NetworkElementType")
        Identifier = apps.get_model("metadata", "ExternalIdentifier")
        User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
        creator = User.objects.create(username="upgrade-creator")
        updater = User.objects.create(username="upgrade-updater")
        deleter = User.objects.create(username="upgrade-deleter")
        north = Department.objects.create(name="Replacement North")
        south = Department.objects.create(name="Replacement South")
        kind = Kind.objects.create(department=north, name="Site")
        parents = [
            Element.objects.create(department=owner, element_type=kind, name=owner.name)
            for owner in (north, south)
        ]

        def add(parent, *, archived=False):
            from django.utils import timezone

            row = Identifier.objects.create(
                network_element=parent, source="ERP", value="replacement-pair",
                deleted_at=timezone.now() if archived else None,
                created_by=creator, updated_by=updater,
                deleted_by=deleter if archived else None,
            )
            ids.append(row.pk)
            return row

        yield Identifier, parents, add
    finally:
        try:
            if ids:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM metadata_externalidentifier WHERE id = ANY(%s)", [ids])
        finally:
            restore_migrations()
            # Django may record both original aliases after applying a
            # replacement. Normalize only aliases absent at fixture entry,
            # after verifying the restored schema above.
            for key in (GLOBAL_UNIQUENESS, TARGET, REPLACEMENT):
                if key not in original_history:
                    recorder.record_unapplied(*key)
            assert set(recorder.applied_migrations()) == original_history
            assert list(
                recorder.migration_qs.exclude(app="metadata").order_by("pk").values()
            ) == unrelated_history


@pytest.mark.postgis
@pytest.mark.django_db(transaction=True)
def test_replacement_preserves_active_and_archived_identifiers_and_reverses(historical_identifiers):
    Identifier, parents, add = historical_identifiers
    for parent in parents:
        add(parent)
        add(parent, archived=True)
        add(parent, archived=True)
    before = list(Identifier.objects.order_by("pk").values())
    before_index = identifier_index()
    executor = MigrationExecutor(connection)
    assert [m.name for m, backwards in executor.migration_plan([REPLACEMENT])] == [REPLACEMENT[1]]
    executor.migrate([REPLACEMENT])
    apps = original_executor().loader.project_state([TARGET]).apps
    CurrentIdentifier = apps.get_model("metadata", "ExternalIdentifier")
    rows = list(CurrentIdentifier.objects.order_by("pk").values())
    owners = {parent.pk: parent.department_id for parent in parents}
    assert [row.pop("department_id") for row in rows] == [
        owners[row["network_element_id"]] for row in before
    ]
    assert rows == before
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, Identifier._meta.db_table)
    assert constraints["meta_active_dept_external_identifier"]["unique"]
    assert constraints["meta_active_dept_external_identifier"]["columns"] == ["department_id", "source", "value"]
    assert constraints["meta_identifier_element_department"]["foreign_key"]
    assert INDEX_NAME not in constraints

    from django.db import transaction

    with pytest.raises(IntegrityError) as duplicate_failure, transaction.atomic():
        CurrentIdentifier.objects.create(
            network_element_id=parents[0].pk, department_id=parents[0].department_id,
            source="ERP", value="replacement-pair",
        )
    assert duplicate_failure.value.__cause__.sqlstate == "23505"
    assert duplicate_failure.value.__cause__.diag.constraint_name == "meta_active_dept_external_identifier"
    with pytest.raises(IntegrityError) as ownership_failure, transaction.atomic():
        CurrentIdentifier.objects.create(
            network_element_id=parents[0].pk, department_id=parents[1].department_id,
            source="ERP", value="wrong-owner",
        )
    assert ownership_failure.value.__cause__.sqlstate == "23503"
    assert ownership_failure.value.__cause__.diag.constraint_name == "meta_identifier_element_department"

    MigrationExecutor(connection).migrate([BASELINE])
    assert list(Identifier.objects.order_by("pk").values()) == before
    assert identifier_index() == before_index


@pytest.mark.postgis
@pytest.mark.django_db(transaction=True)
def test_replacement_rejects_same_department_duplicates_atomically(historical_identifiers):
    Identifier, parents, add = historical_identifiers
    Element = type(parents[0])
    extra = Element.objects.create(
        department_id=parents[0].department_id,
        element_type_id=parents[0].element_type_id, name="Second North site",
    )
    add(parents[0])
    add(extra)
    before = list(Identifier.objects.order_by("pk").values())
    history = list(MigrationRecorder.Migration.objects.order_by("pk").values())
    index = identifier_index()
    with pytest.raises(IntegrityError) as failure:
        MigrationExecutor(connection).migrate([REPLACEMENT])
    assert failure.value.__cause__.sqlstate == "23505"
    assert failure.value.__cause__.diag.constraint_name == "meta_active_dept_external_identifier"
    assert list(Identifier.objects.order_by("pk").values()) == before
    assert list(MigrationRecorder.Migration.objects.order_by("pk").values()) == history
    assert identifier_index() == index


@pytest.mark.postgis
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("starting_point", [GLOBAL_UNIQUENESS, TARGET])
def test_existing_original_migration_history_is_supported(historical_identifiers, starting_point):
    Identifier, parents, add = historical_identifiers
    add(parents[0])
    before = list(Identifier.objects.values())
    assert REPLACEMENT not in MigrationRecorder(connection).applied_migrations()
    original_executor().migrate([starting_point])
    applied = MigrationRecorder(connection).applied_migrations()
    assert GLOBAL_UNIQUENESS in applied
    assert (TARGET in applied) == (starting_point == TARGET)
    assert REPLACEMENT not in applied
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    assert [m.name for m, backwards in plan] == ([TARGET[1]] if starting_point == GLOBAL_UNIQUENESS else [])
    executor.migrate(executor.loader.graph.leaf_nodes())
    assert REPLACEMENT in MigrationRecorder(connection).applied_migrations()
    apps = original_executor().loader.project_state([TARGET]).apps
    rows = list(apps.get_model("metadata", "ExternalIdentifier").objects.values())
    assert [row.pop("department_id") for row in rows] == [parents[0].department_id]
    assert rows == before


@pytest.mark.postgis
@pytest.mark.django_db(transaction=True)
def test_fresh_metadata_install_matches_models():
    from django.apps import apps
    from django.db.migrations.autodetector import MigrationAutodetector
    from django.db.migrations.state import ProjectState

    targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
    try:
        MigrationExecutor(connection).migrate([("metadata", None)])
        executor = MigrationExecutor(connection)
        assert REPLACEMENT in executor.loader.graph.nodes
        assert GLOBAL_UNIQUENESS not in executor.loader.graph.nodes
        executor.migrate(targets)
        executor = MigrationExecutor(connection)
        changes = MigrationAutodetector(
            executor.loader.project_state(), ProjectState.from_apps(apps),
        )._detect_changes()
        assert "metadata" not in changes
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, "metadata_externalidentifier")
        assert "meta_active_dept_external_identifier" in constraints
        assert "meta_identifier_element_department" in constraints
    finally:
        MigrationExecutor(connection).migrate(targets)
