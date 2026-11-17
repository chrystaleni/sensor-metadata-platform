"""Department isolation for identifiers, imports, constraints and migration 0005."""

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

from .test_identifier_upgrade import original_executor, restore_migrations
from django.utils import timezone

from metadata.models import ExternalIdentifier, NetworkElement
from metadata.serializers import NetworkElementSerializer
from metadata.tests.test_backend import API, FixturePolicy, make_workbook
from metadata.tests.test_error_contract import database_snapshot, scenario
from rest_framework.test import APIClient


pytestmark = pytest.mark.postgis
PAIR = {"source": "ERP", "value": "tenant-private-101"}
BEFORE = ("metadata", "0004_identifier_system_uniqueness")
AFTER = ("metadata", "0005_identifier_department_scope")


class PartitionPolicy(FixturePolicy):
    def readable_department_ids(self, request):
        if request.user.get_username() == "south":
            return (3,)
        return super().readable_department_ids(request)

    def writable_department_ids(self, request):
        if request.user.get_username() == "south":
            return (3,)
        return super().writable_department_ids(request)


@pytest.fixture
def partition(scenario, settings):
    settings.METADATA_ACCESS_POLICY = "metadata.tests.test_identifier_departments.PartitionPolicy"
    scenario["users"]["south"] = get_user_model().objects.create_user(username="south")
    scenario["south_element"] = NetworkElement.objects.get(pk=scenario["tokens"]["other_network_element"])
    return scenario


def submit(partition, mode, pair=PAIR, *, department=2, actor="editor"):
    client = partition["client"]
    client.force_authenticate(partition["users"][actor])
    if mode == "import":
        upload = make_workbook({"Network Elements": [
            ("name", "element_type", "external_identifiers"),
            ("Imported identifier", partition["catalog"]["element_type"], json.dumps([pair])),
        ]})
        return client.post(f"{API}imports/excel/", {"department": department, "file": upload}, format="multipart")
    if mode == "PATCH":
        element = partition["records"]["network-elements"] if department == 2 else partition["south_element"]
        return client.patch(f"{API}network-elements/{element.pk}/", {
            "name": "Identifier update", "external_identifiers": [pair],
        }, format="json")
    return client.post(f"{API}network-elements/", {
        "department": department, "name": "New identifier", "element_type": partition["catalog"]["element_type"],
        "external_identifiers": [pair],
    }, format="json")


@pytest.mark.parametrize("mode", ["POST", "PATCH", "import"])
@pytest.mark.parametrize("actor", ["editor", "multi"])
def test_other_department_identifier_does_not_change_success(partition, mode, actor):
    hidden = ExternalIdentifier.objects.create(network_element=partition["south_element"], **PAIR)
    before_hidden = ExternalIdentifier.objects.filter(pk=hidden.pk).values().get()
    client = partition["client"]
    client.force_authenticate(partition["users"]["editor"])
    assert client.get(f'{API}network-elements/{partition["south_element"].pk}/').status_code == 404
    assert client.get(f"{API}network-elements/", {"identifier": PAIR["value"]}).json()["count"] == 0
    response = submit(partition, mode, actor=actor)
    assert response.status_code == (200 if mode == "PATCH" else 201), response.content
    assert set(ExternalIdentifier.objects.active().filter(**PAIR).values_list("department_id", flat=True)) == {2, 3}
    assert ExternalIdentifier.objects.filter(pk=hidden.pk).values().get() == before_hidden
    for user, expected_department in (("editor", 2), ("south", 3)):
        client.force_authenticate(partition["users"][user])
        result = client.get(f"{API}network-elements/", {"identifier": PAIR["value"]}).json()
        assert result["count"] == 1
        assert result["results"][0]["department"] == expected_department


@pytest.mark.parametrize("mode", ["POST", "PATCH", "import"])
def test_same_department_duplicate_rejects_and_preserves_rows(partition, mode):
    parent = NetworkElement.objects.create(department_id=2, name="Existing claim",
                                          element_type_id=partition["catalog"]["element_type"])
    ExternalIdentifier.objects.create(network_element=parent, **PAIR)
    before = database_snapshot()
    response = submit(partition, mode)
    assert response.status_code == 400, response.content
    body = response.json()
    if mode == "import":
        assert (body["errors"][0]["sheet"], body["errors"][0]["row"]) == ("Network Elements", 2)
        body = body["errors"][0]["errors"]
    assert body["external_identifiers"] == ["An active identifier with this source and value already exists."]
    assert database_snapshot() == before


@pytest.mark.parametrize("mode", ["POST", "PATCH", "import"])
def test_identifier_validation_cannot_bypass_department_permission(partition, mode):
    ExternalIdentifier.objects.create(network_element=partition["south_element"], **PAIR)
    before = database_snapshot()
    response = submit(partition, mode, department=3)
    assert response.status_code == (404 if mode == "PATCH" else 403)
    assert set(response.json()) == {"detail"}
    assert database_snapshot() == before


def test_database_scopes_uniqueness_and_keeps_archived_history(partition):
    north = partition["records"]["network-elements"]
    old = ExternalIdentifier.objects.create(network_element=north, **PAIR)
    south = ExternalIdentifier.objects.create(network_element=partition["south_element"], **PAIR)
    assert (old.department_id, south.department_id) == (2, 3)
    before = database_snapshot()
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        ExternalIdentifier.objects.create(network_element=north, **PAIR)
    assert caught.value.__cause__.sqlstate == "23505"
    assert caught.value.__cause__.diag.constraint_name == "meta_active_dept_external_identifier"
    assert database_snapshot() == before
    ExternalIdentifier.objects.filter(pk=old.pk).archive(partition["users"]["editor"])
    replacement = ExternalIdentifier.objects.create(network_element=north, **PAIR)
    old.refresh_from_db()
    assert old.deleted_at is not None
    assert old.deleted_by_id == partition["users"]["editor"].pk
    assert replacement.pk != old.pk
    assert ExternalIdentifier.objects.active().filter(**PAIR).count() == 2


@pytest.mark.parametrize("operation", ["bulk-create", "change-department", "change-parent", "clear-department"])
def test_database_rejects_identifier_parent_department_mismatch(partition, operation):
    before = database_snapshot()
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        if operation == "bulk-create":
            ExternalIdentifier.objects.bulk_create([
                ExternalIdentifier(department_id=2, network_element=partition["south_element"], **PAIR),
            ])
        else:
            record = ExternalIdentifier.objects.filter(network_element=partition["records"]["network-elements"])
            changes = {"department_id": None} if operation == "clear-department" else (
                {"department_id": 3} if operation == "change-department" else
                {"network_element_id": partition["south_element"].pk}
            )
            record.update(**changes)
    if operation == "clear-department":
        assert caught.value.__cause__.sqlstate == "23502"
        assert caught.value.__cause__.diag.column_name == "department_id"
    else:
        assert caught.value.__cause__.sqlstate == "23503"
        assert caught.value.__cause__.diag.constraint_name == "meta_identifier_element_department"
    assert database_snapshot() == before


def test_nested_department_is_derived_from_parent(partition):
    response = submit(partition, "POST", {**PAIR, "department": 3})
    assert response.status_code == 201, response.content
    identifier = ExternalIdentifier.objects.get(network_element_id=response.json()["id"])
    assert identifier.department_id == identifier.network_element.department_id == 2
    assert set(response.json()["external_identifiers"][0]) == {"id", "source", "value"}


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("importing", [False, True], ids=["API", "Excel"])
def test_concurrent_different_departments_claim_independently(partition, importing):
    def south_write():
        try:
            local = {**partition, "client": APIClient()}
            return submit(local, "import" if importing else "POST", department=3, actor="south")
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as worker:
        with transaction.atomic():
            north = submit(partition, "POST")
            assert north.status_code == 201, north.content
            # South must complete while North remains uncommitted. A global
            # unique index would block here and disclose the other claim.
            south = worker.submit(south_write).result(timeout=5)
            assert south.status_code == 201, south.content
    assert set(ExternalIdentifier.objects.active().filter(**PAIR).values_list("department_id", flat=True)) == {2, 3}


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("importing", [False, True], ids=["API", "Excel"])
def test_direct_writer_collision_returns_scoped_error_with_rollback(partition, monkeypatch, importing):
    parent = NetworkElement.objects.create(department_id=2, name="Direct writer parent",
                                          element_type_id=partition["catalog"]["element_type"])
    before = database_snapshot()
    validated, committed = Event(), Event()
    original = NetworkElementSerializer.save_identifiers

    def pause_after_validation(serializer, element, identifiers):
        validated.set()
        assert committed.wait(5), "Direct database writer did not complete"
        return original(serializer, element, identifiers)

    # Instrument scheduling only: both writers still use real transactions,
    # the real unique index and the production persistence/error handler.
    monkeypatch.setattr(NetworkElementSerializer, "save_identifiers", pause_after_validation)

    def claim_directly():
        try:
            assert validated.wait(5)
            with transaction.atomic():
                identifier = ExternalIdentifier.objects.create(network_element=parent, **PAIR)
            committed.set()
            return identifier.pk
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as worker:
        future = worker.submit(claim_directly)
        response = submit(partition, "import" if importing else "PATCH")
        legitimate_claim_id = future.result(timeout=5)
    assert response.status_code == 400, response.content
    body = response.json()
    if importing:
        assert (body["errors"][0]["sheet"], body["errors"][0]["row"]) == ("Network Elements", 2)
        body = body["errors"][0]["errors"]
    assert body["external_identifiers"] == ["An active identifier with this source and value already exists."]
    after = database_snapshot()
    rows = json.loads(after["metadata.ExternalIdentifier"])
    after["metadata.ExternalIdentifier"] = json.dumps(
        [row for row in rows if row["id"] != legitimate_claim_id], sort_keys=True,
    )
    assert after == before, "Rejected request must roll back everything except the independent writer's committed claim"


@pytest.mark.django_db(transaction=True)
def test_migration_backfills_active_and_archived_identifiers_without_data_loss():
    executor = original_executor()
    executor.migrate([BEFORE])
    try:
        apps = executor.loader.project_state([BEFORE]).apps
        department = apps.get_model("local_departments", "Department")
        department.objects.bulk_create([department(pk=1, name="Platform"), department(pk=2, name="North"),
                                        department(pk=3, name="South")])
        kind = apps.get_model("metadata", "NetworkElementType").objects.create(department_id=1, name="Site")
        element = apps.get_model("metadata", "NetworkElement")
        parents = [element.objects.create(department_id=dept, name=f"Site {dept}", element_type=kind) for dept in (2, 3)]
        identifier = apps.get_model("metadata", "ExternalIdentifier")
        identifier.objects.create(network_element=parents[0], source="ERP", value="active")
        identifier.objects.create(network_element=parents[1], source="ERP", value="archived", deleted_at=timezone.now())
        before = list(identifier.objects.order_by("pk").values())
        original_executor().migrate([AFTER])
        apps = original_executor().loader.project_state([AFTER]).apps
        migrated = list(apps.get_model("metadata", "ExternalIdentifier").objects.order_by("pk").values())
        assert [record.pop("department_id") for record in migrated] == [2, 3]
        assert migrated == before
        original_executor().migrate([BEFORE])
        assert list(identifier.objects.order_by("pk").values()) == before
    finally:
        restore_migrations()


@pytest.mark.django_db(transaction=True)
def test_reverse_migration_refuses_global_collision_without_changing_data(partition):
    ExternalIdentifier.objects.create(network_element=partition["records"]["network-elements"], **PAIR)
    ExternalIdentifier.objects.create(network_element=partition["south_element"], **PAIR)
    before = database_snapshot()
    try:
        with pytest.raises(IntegrityError):
            original_executor().migrate([BEFORE])
        assert AFTER in MigrationRecorder(connection).applied_migrations()
        assert database_snapshot() == before
    finally:
        restore_migrations()
