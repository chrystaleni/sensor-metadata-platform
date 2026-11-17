# PR #27: Department-scoped external identifiers

Argyris Fellas, 15 November 2026. Baseline `e9c258f`; the assignee requested this privacy correction before merge. No approval by another team member is implied.

## Rule and requirement interpretation

An active `(source,value)` may identify only one Network Element **within its Department**. The same pair may exist independently in another Department. This remains true when the caller has access to both Departments: validation uses the selected write Department, not all readable Departments.

BE-05 #5 says to reject duplicate identifiers for the same external system but does not explicitly require a global namespace. The assignee's latest instruction clarifies that rule as Department-scoped to avoid revealing another Department's claim through a duplicate error. This supersedes the earlier global interpretation in migration 0004 and historical audit records.

The serializer now queries active identifiers only in its target Department. Excel imports already reuse that serializer and the same transactional persistence path, so they follow exactly the same rule. Duplicate error wording and nested `{id,source,value}` responses are unchanged. Ownership is assigned from the Network Element; a nested ownership value cannot change it. Missing source/value on PATCH still returns 400 with unchanged data; omitted/empty lists keep their existing semantics.

## New migration 0005

`0005_identifier_department_scope` adds a Department FK to ExternalIdentifier, backfills **all** rows from their Network Elements, makes ownership non-null and replaces the old unique index with:

```text
UNIQUE (department_id, source, value) WHERE deleted_at IS NULL
```

A composite FK `(department_id,network_element_id)` references the existing unique `(department_id,id)` key on NetworkElement. It rejects mismatched ownership even for direct SQL, queryset updates or bulk writes. Ordinary ORM saves derive omitted ownership from the parent; bulk writers supply it explicitly. The production serializer's bulk insert always uses the parent's Department.

Migrations 0001-0004 remain byte-for-byte unchanged. No shared Department/User model, frontend, API endpoint or CI workflow was changed. All migration execution during this work used separate local/test databases.

Backfill preserves IDs, values, audit fields and archived rows. Reversal to 0004 restores global uniqueness and will fail atomically if different Departments now contain the same active pair. No automatic deletion/merging is performed. Agree a backup/data-owner plan before any real downgrade. Published main still has the intermediate original 0004 limitation. PR #32 supplies a replacement path for databases at 0003; the [database upgrade runbook](argyris-database.md#select-the-path-from-the-actual-migration-history) distinguishes that path from original-0004, original-0005 and fresh histories.

## PR #32 upgrade compatibility follow-up

Reviewed replacement revision: `e4fa5de50f0bdeec81526e329792e673e7ae3f67`, 17 November 2026. PR #32 remains separate from the merged PR #27 at this review point.

The new `0004_squashed_0005_identifier_department_scope` replaces original 0004/0005 while leaving both files unchanged. For a database at 0003, it installs the final Department-scoped constraints directly, preserving legitimate cross-Department reuse and archived identifiers. A same-Department active collision still rejects the upgrade atomically.

Django completes a partially applied original pair through original 0005; a fully applied original pair already has the required schema. Fresh installations use the replacement. Follow the [complete runbook](argyris-database.md#migration-history-and-pr-32-upgrade-runbook) for preflight, backups, history inspection, validation and path-specific rollback limitations. The previous global duplicate query applies to the historical global rule, not the replacement's Department-scoped acceptance criterion.

`metadata/tests/test_identifier_upgrade.py` covers the historical failure, all four installation histories, data/actor/timestamp preservation, same-Department collisions, database ownership constraints and replacement reversal. Its migration-history helpers are test-only. This follow-up does not change API/Excel identifier validation or request/response fields.

## Regression evidence

The table groups all parameter combinations in `backend/metadata/tests/test_identifier_departments.py`; the [result index](../testing/identifier-department-results.json) lists all 24 exact, independently executable pytest node IDs. Run the file with `python -m pytest -v metadata/tests/test_identifier_departments.py` from `backend/` using the documented isolated PostGIS environment.

| Test / parameter | Cases | Expected behavior and integrity |
| --- | --- | --- |
| `test_other_department_identifier_does_not_change_success[editor/multi-POST/PATCH/import]` | 6 | Hidden Department's identifier remains unreadable and unchanged; North can reuse the pair (201 create/import or 200 PATCH). Even a multi-Department caller validates only the target Department. Each single-Department user searches and sees only its own match. |
| `test_same_department_duplicate_rejects_and_preserves_rows[POST/PATCH/import]` | 3 | Same-Department duplicate returns 400 with the existing field/row error; complete metadata snapshot remains unchanged. |
| `test_identifier_validation_cannot_bypass_department_permission[POST/PATCH/import]` | 3 | Unauthorized Department creation/import returns 403; hidden detail PATCH returns 404. No identifier-validation information or saved changes. |
| `test_database_scopes_uniqueness_and_keeps_archived_history` | 1 | Cross-Department pair is accepted; same-Department duplicate raises SQLSTATE 23505. Archival preserves the old row and permits replacement. |
| `test_database_rejects_identifier_parent_department_mismatch[bulk-create/change-department/change-parent/clear-department]` | 4 | Composite FK rejects inconsistent ownership (23503); NOT NULL rejects missing Department (23502). All metadata remains unchanged. |
| `test_nested_department_is_derived_from_parent` | 1 | Supplied nested Department cannot override ownership; response shape stays unchanged. |
| `test_concurrent_different_departments_claim_independently[API/Excel]` | 2 | South commits the same pair while North's transaction is still open; no global unique-index blocking or duplicate response. |
| `test_direct_writer_collision_returns_scoped_error_with_rollback[API/Excel]` | 2 | A real independent same-Department writer claims the pair after API validation. The new unique index rejects the loser; API returns 400 or Excel returns a 400 row error, rolling back the losing parent's edits/identifier archival. Only the independent writer's legitimate commit remains. Scheduling is instrumented; responses, writes and constraints are real. |
| `test_migration_backfills_active_and_archived_identifiers_without_data_loss` | 1 | Historical 0004 rows migrate to the matching Department; existing fields remain identical. Reverse/reapply succeeds when globally compatible. |
| `test_reverse_migration_refuses_global_collision_without_changing_data` | 1 | A conflicting downgrade raises IntegrityError atomically; 0005 stays applied and all records/constraints remain usable. |

The six cross-Department POST/PATCH/Excel cases first failed against the baseline because it returned a duplicate 400 for another Department's identifier. They pass after the correction. Existing uniqueness and concurrent-collision tests were updated to use two writers in the **same** Department, retaining their intended rejection assertions. The error-catalog duplicate fixture likewise uses another element in the selected Department.

Local validation on Python 3.13.18, Django 5.2.19 and PostgreSQL 16.15/PostGIS 3.4.6: **383 tests and 18 subtests passed, zero failures**. Dependency/system checks, migration application through 0005 and `makemigrations --check --dry-run` passed. These local results do not assert that GitHub Actions has completed; remote checks must be observed on the published head.

## Integration and merge boundary

The default authorization adapter still denies access. Real memberships, role mapping and the shared Department decision remain the security/architecture owner's integration work, documented in the [shared handover](pr27-shared-integration.md). This correction does not grant access or redesign that boundary. Merge uses the repository's existing checks and required-review rules; no bypass or fabricated approval is authorized.
