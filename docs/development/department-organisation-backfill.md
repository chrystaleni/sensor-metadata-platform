# Backfill Department Organisations

Migration `local_departments.0003_backfill_department_organisations` assigns Organisation ownership to existing Departments in place. On an empty Department table it can run without a manifest. It ensures the Organisation with code `platform` and name `Platform` exists. Platform Department provisioning is a separate step.

For a populated database, obtain approval for the exact Department ID to Organisation code mapping for that installation. Supply it to the migration process in `DEPARTMENT_ORGANISATION_BACKFILL`. Keep the approved manifest outside the repository.

The manifest contains two JSON objects and, when applicable, a verified Platform Department ID.

- `organisations` maps each approved non-Platform Organisation code to its name. The `platform` code is built in. If declared explicitly, its name must be `Platform`.
- `departments` maps every existing Department ID, written as a positive decimal JSON string key, to its approved Organisation code.
- `platform_department_id` is the verified existing Department ID as a JSON integer. Supply it whenever controlled-list rows exist or a Department maps to `platform`.

Illustrative example:

```json
{
  "organisations": {"water": "Water Services"},
  "departments": {"41": "water", "83": "platform"},
  "platform_department_id": 83
}
```

With the approved manifest file available to the operator, run from `backend/` using the configuration for the intended database:

```sh
DEPARTMENT_ORGANISATION_BACKFILL="$(cat /path/to/approved-backfill.json)" python manage.py migrate
```

Before migration, compare the installation's configured shared catalog owner with the stored Department IDs across all four controlled lists, including archived entries. Use the existing Department inventory to confirm the owner. This read-only query lists ownership and works regardless of the Department's display name.

```sql
SELECT 'measurement_type' AS catalog, department_id FROM metadata_measurementtype
UNION
SELECT 'measurement_unit', department_id FROM metadata_measurementunit
UNION
SELECT 'physical_device_type', department_id FROM metadata_physicaldevicetype
UNION
SELECT 'network_element_type', department_id FROM metadata_networkelementtype
ORDER BY 1, 2;
```

When the query returns rows, all owner IDs must agree with the verified ID in the manifest. Resolve any discrepancy with the data owner before migration. If the lists are empty and a Platform Department already exists, confirm its ID with the operator and declare it explicitly. Map the verified ID to `platform` and reserve that code for that Department. The example IDs are illustrative.

The migration rejects invalid JSON, duplicate keys, incomplete mappings, unknown IDs, undeclared codes, conflicting Organisation names, conflicting existing assignments and invalid Platform ownership before writing. Run the migration while Department, Organisation and controlled-list writers are stopped so the inventory stays stable. On rejection, correct the approved input and retry. Reversing only the data migration retains the assignments and Organisations so previously valid data is preserved.
