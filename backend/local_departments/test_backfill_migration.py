import json

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import QuerySet


BEFORE = ("local_departments", "0002_organisation_department_organisation")
AFTER = ("local_departments", "0003_backfill_department_organisations")
METADATA = ("metadata", "0004_identifier_system_uniqueness")
MANIFEST = "DEPARTMENT_ORGANISATION_BACKFILL"


@pytest.fixture
def backfill(monkeypatch, transactional_db):
    executor = MigrationExecutor(connection)
    original_targets = executor.loader.graph.leaf_nodes()
    executor.migrate([BEFORE, METADATA])
    apps = executor.loader.project_state([BEFORE, METADATA]).apps
    department = apps.get_model("local_departments", "Department")
    organisation = apps.get_model("local_departments", "Organisation")
    device = apps.get_model("metadata", "PhysicalDevice")
    device_type = apps.get_model("metadata", "PhysicalDeviceType")
    # Isolate both empty and populated cases from any previously provisioned identity.
    organisation.objects.all().delete()
    monkeypatch.delenv(MANIFEST, raising=False)

    try:
        yield department, organisation, device, device_type
    finally:
        device.objects.all().delete()
        device_type.objects.all().delete()
        apps.get_model("metadata", "MeasurementUnit").objects.all().delete()
        department.objects.all().delete()
        organisation.objects.all().delete()
        monkeypatch.delenv(MANIFEST, raising=False)
        MigrationExecutor(connection).migrate(original_targets)


def test_empty_database_creates_only_platform_organisation(backfill):
    department, organisation, _, _ = backfill

    MigrationExecutor(connection).migrate([AFTER])

    assert list(organisation.objects.values_list("code", "name")) == [("platform", "Platform")]
    assert not department.objects.exists()


def test_approved_backfill_preserves_department_ids_and_metadata(backfill, monkeypatch):
    department, organisation, device, device_type = backfill
    department.objects.create(id=1, name="North")
    platform = department.objects.create(id=83, name="Shared Reference Data")
    regional = organisation.objects.create(code="regional", name="Regional Authority")
    department.objects.create(id=42, name="South", organisation=regional)
    catalog = device_type.objects.create(name="Station", department=platform)
    record = device.objects.create(name="Meter", department_id=1, device_type=catalog)
    monkeypatch.setenv(MANIFEST, json.dumps({
        "organisations": {"water": "Water Services", "regional": "Regional Authority"},
        "departments": {"1": "water", "42": "regional", "83": "platform"},
        "platform_department_id": 83,
    }))

    MigrationExecutor(connection).migrate([AFTER])

    assert list(department.objects.order_by("id").values_list("id", "organisation__code")) == [
        (1, "water"), (42, "regional"), (83, "platform"),
    ]
    record.refresh_from_db()
    catalog.refresh_from_db()
    assert record.department_id == 1
    assert record.device_type_id == catalog.pk
    assert catalog.department_id == 83
    assert department.objects.get(pk=42).organisation_id == regional.pk
    assert set(organisation.objects.values_list("code", "name")) == {
        ("water", "Water Services"), ("regional", "Regional Authority"), ("platform", "Platform"),
    }


@pytest.mark.parametrize(("assignments", "message"), [
    (None, r"approved mapping is required"),
    ({"41": "water"}, r"missing Department IDs \[83\]"),
    ({"41": "water", "83": "platform", "99": "water"}, r"unknown Department IDs \[99\]"),
    ({"41": "unknown", "83": "platform"}, r"undeclared Organisation code 'unknown'"),
    ({"41": "platform", "83": "platform"}, r"invalid Platform ownership for Department 41"),
    ({"41": "water", "83": "water"}, r"invalid Platform ownership for Department 83"),
    ({"41": "water", "83": "platform"}, r"Department 83 already has a conflicting"),
])
def test_invalid_backfill_leaves_database_unchanged(backfill, monkeypatch, assignments, message):
    department, organisation, _, _ = backfill
    department.objects.create(id=41, name="North")
    prior_owner = organisation.objects.create(code="legacy", name="Legacy")
    department.objects.create(id=83, name="Platform", organisation=prior_owner)
    if assignments is not None:
        monkeypatch.setenv(MANIFEST, json.dumps({
            "organisations": {"water": "Water Services"},
            "departments": assignments,
            "platform_department_id": 83,
        }))

    with pytest.raises(ValueError, match=message):
        MigrationExecutor(connection).migrate([AFTER])

    assert list(department.objects.order_by("id").values_list("id", "organisation_id")) == [
        (41, None), (83, prior_owner.pk),
    ]
    assert list(organisation.objects.values_list("code", flat=True)) == ["legacy"]
    assert AFTER not in MigrationExecutor(connection).loader.applied_migrations


@pytest.mark.parametrize(("platform_id", "conflicting_owner", "message"), [
    (None, False, "platform_department_id is required"),
    (99, False, "platform_department_id must be an existing Department ID"),
    (1, False, "controlled-list ownership"),
    (83, True, "controlled-list ownership"),
])
def test_backfill_requires_verified_catalog_owner(backfill, monkeypatch, platform_id, conflicting_owner, message):
    department, organisation, _, device_type = backfill
    ordinary = department.objects.create(id=1, name="North")
    platform = department.objects.create(id=83, name="Shared Reference Data")
    device_type.objects.create(name="Station", department=platform)
    if conflicting_owner:
        apps = MigrationExecutor(connection).loader.project_state([BEFORE, METADATA]).apps
        apps.get_model("metadata", "MeasurementUnit").objects.create(
            name="Metres", symbol="m", department_id=ordinary.pk,
        )
    manifest = {
        "organisations": {"water": "Water Services"},
        "departments": {"1": "water", "83": "platform"} if platform_id != 1 else {"1": "platform", "83": "water"},
    }
    if platform_id is not None:
        manifest["platform_department_id"] = platform_id
    else:
        manifest["departments"]["83"] = "water"
    monkeypatch.setenv(MANIFEST, json.dumps(manifest))

    with pytest.raises(ValueError, match=message):
        MigrationExecutor(connection).migrate([AFTER])

    assert not organisation.objects.exists()
    assert not department.objects.filter(organisation__isnull=False).exists()
    assert device_type.objects.get().department_id == 83
    assert AFTER not in MigrationExecutor(connection).loader.applied_migrations


def test_backfill_rolls_back_after_database_writes(backfill, monkeypatch):
    department, organisation, _, device_type = backfill
    platform = department.objects.create(id=83, name="Shared Reference Data")
    device_type.objects.create(name="Station", department=platform)
    monkeypatch.setenv(MANIFEST, json.dumps({
        "organisations": {},
        "departments": {"83": "platform"},
        "platform_department_id": 83,
    }))
    bulk_update = QuerySet.bulk_update

    def fail_after_update(queryset, *args, **kwargs):
        bulk_update(queryset, *args, **kwargs)
        assert organisation.objects.filter(code="platform").exists()
        assert department.objects.get(pk=83).organisation_id is not None
        raise RuntimeError("Injected failure after backfill writes")

    with monkeypatch.context() as patch:
        patch.setattr(QuerySet, "bulk_update", fail_after_update)
        with pytest.raises(RuntimeError, match="Injected failure after backfill writes"):
            MigrationExecutor(connection).migrate([AFTER])

    assert not organisation.objects.exists()
    assert department.objects.get(pk=83).organisation_id is None
    assert device_type.objects.get().department_id == 83
    assert AFTER not in MigrationExecutor(connection).loader.applied_migrations
