import json
import os

from django.db import migrations


MANIFEST_ENV = "DEPARTMENT_ORGANISATION_BACKFILL"
PLATFORM_CODE = "platform"
PLATFORM_NAME = "Platform"
CONTROLLED_LIST_MODELS = ("MeasurementType", "MeasurementUnit", "PhysicalDeviceType", "NetworkElementType")


def invalid_manifest(message):
    return ValueError(f"{MANIFEST_ENV}: {message}")


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise invalid_manifest(f"duplicate JSON key {key!r}.")
        result[key] = value
    return result


def valid_text(value):
    return (
        isinstance(value, str)
        and 0 < len(value) <= 120
        and value == value.strip()
        and "\x00" not in value
        and not any("\ud800" <= char <= "\udfff" for char in value)
    )


def read_manifest(department_ids):
    raw = os.environ.get(MANIFEST_ENV)
    if raw is None:
        if department_ids:
            raise invalid_manifest(
                f"an approved mapping is required for existing Department IDs {sorted(department_ids)}."
            )
        return {PLATFORM_CODE: PLATFORM_NAME}, {}, None

    try:
        manifest = json.loads(raw, object_pairs_hook=unique_keys)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise invalid_manifest("expected a valid JSON object.") from exc

    required = {"organisations", "departments"}
    if not isinstance(manifest, dict) or not required <= manifest.keys() <= required | {"platform_department_id"}:
        raise invalid_manifest("expected organisations, departments and an optional platform_department_id.")
    platform_id = manifest.get("platform_department_id")
    if "platform_department_id" in manifest and (type(platform_id) is not int or platform_id not in department_ids):
        raise invalid_manifest("platform_department_id must be an existing Department ID.")
    names = manifest["organisations"]
    claims = manifest["departments"]
    if not isinstance(names, dict) or not isinstance(claims, dict):
        raise invalid_manifest("organisations and departments must both be JSON objects.")
    for code, name in names.items():
        if not valid_text(code) or not valid_text(name):
            raise invalid_manifest("Organisation codes and names must be non-empty strings of up to 120 characters.")
    if names.get(PLATFORM_CODE, PLATFORM_NAME) != PLATFORM_NAME:
        raise invalid_manifest("Organisation code 'platform' must have name 'Platform'.")
    names[PLATFORM_CODE] = PLATFORM_NAME

    assignments = {}
    for identifier, code in claims.items():
        if (
            not identifier.isascii()
            or not identifier.isdecimal()
            or identifier.startswith("0")
            or len(identifier) > 19
            or int(identifier) > 2**63 - 1
        ):
            raise invalid_manifest(f"invalid Department ID {identifier!r}; use a positive bigint as a JSON key.")
        if not isinstance(code, str) or code not in names:
            raise invalid_manifest(f"Department {identifier} refers to an undeclared Organisation code {code!r}.")
        assignments[int(identifier)] = code

    missing = department_ids - assignments.keys()
    unknown = assignments.keys() - department_ids
    if missing or unknown:
        raise invalid_manifest(f"missing Department IDs {sorted(missing)}; unknown Department IDs {sorted(unknown)}.")
    return names, assignments, platform_id


def validate_platform_ownership(apps, alias, assignments, platform_id):
    owners = set()
    for model_name in CONTROLLED_LIST_MODELS:
        catalog = apps.get_model("metadata", model_name)
        owners.update(catalog.objects.using(alias).order_by().values_list("department_id", flat=True).distinct())

    if (owners or PLATFORM_CODE in assignments.values()) and platform_id is None:
        raise invalid_manifest("platform_department_id is required for existing shared catalog ownership or Platform assignments.")
    if owners and owners != {platform_id}:
        raise invalid_manifest(
            f"controlled-list ownership {sorted(owners)} does not match declared platform_department_id {platform_id}."
        )
    for department_id, code in assignments.items():
        if (department_id == platform_id) != (code == PLATFORM_CODE):
            raise invalid_manifest(
                f"invalid Platform ownership for Department {department_id}; "
                "only the declared Platform Department may map to Organisation 'platform', and it must map there."
            )


def backfill_departments(apps, schema_editor):
    alias = schema_editor.connection.alias
    departments = apps.get_model("local_departments", "Department").objects.using(alias)
    organisations = apps.get_model("local_departments", "Organisation").objects.using(alias)
    existing_departments = list(departments.select_for_update().order_by("pk"))
    names, assignments, platform_id = read_manifest({department.pk for department in existing_departments})
    validate_platform_ownership(apps, alias, assignments, platform_id)
    existing_organisations = {
        organisation.code: organisation
        for organisation in organisations.select_for_update().filter(code__in=names).order_by("pk")
    }
    for code, organisation in existing_organisations.items():
        if organisation.name != names[code]:
            raise invalid_manifest(f"Organisation {code!r} already exists with a different name.")

    for department in existing_departments:
        code = assignments[department.pk]
        organisation = existing_organisations.get(code)
        if department.organisation_id is not None and (
            organisation is None or department.organisation_id != organisation.pk
        ):
            raise invalid_manifest(f"Department {department.pk} already has a conflicting Organisation assignment.")

    for code, name in names.items():
        if code not in existing_organisations:
            existing_organisations[code] = organisations.create(code=code, name=name)
    unassigned = [department for department in existing_departments if department.organisation_id is None]
    for department in unassigned:
        department.organisation_id = existing_organisations[assignments[department.pk]].pk
    departments.bulk_update(unassigned, ["organisation"])


class Migration(migrations.Migration):
    atomic = True
    dependencies = [
        ("local_departments", "0002_organisation_department_organisation"),
        ("metadata", "0004_identifier_system_uniqueness"),
    ]
    operations = [migrations.RunPython(backfill_departments, reverse_code=migrations.RunPython.noop)]
