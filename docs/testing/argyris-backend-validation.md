# Backend validation and acceptance mapping

Argyris Fellas, 13 November 2026. Scope is BE-01 through BE-08 in PR #27. The backend was audited against the actual GitHub issue bodies. Closing the issues at the assignee's request does not signify teammate approval, a merged PR or a deployed application.

## Executed checks

The final local run used Python 3.12.14, Django 5.2.19, pytest 9.2.0, PostgreSQL 16.15, PostGIS 3.4.6 and GDAL 3.12.4. A newly initialized disposable PostGIS database was used for migrations; pytest created its own separate test database. No shared database was reset or modified.

| Command | Observed result |
| --- | --- |
| `python -m pip check` | No broken requirements. |
| `python manage.py check` | No issues; 0 silenced. |
| `python manage.py migrate --noinput` | All migrations, including 0004, applied successfully. |
| `python manage.py makemigrations --check --dry-run` | No changes detected. |
| `python -m pytest -v` | **36 passed, 9 subtests passed.** |
| `python manage.py migrate metadata 0003` then `0004` | Reversed and reapplied the new uniqueness migration successfully in the disposable database. |

The original four database/health tests remain included. New tests do not replace them. CI runs the same backend checks on branch pushes and PRs to `main`; the [PR checks page](https://github.com/chrystaleni/sensor-metadata-platform/pull/27/checks) is the current remote result. The existing frontend job remains unchanged.

## Acceptance mapping

Test names below are in `backend/metadata/tests/test_backend.py` unless stated otherwise.

| Issue | Implemented and exercised | Representative evidence | Shared review still needed |
| --- | --- | --- | --- |
| BE-01 #1 | Required links, PostGIS geometry, optional accounts, audit fields and migrations. | `test_database_rejects_cross_department_measurements`, `test_database_rejects_unsupported_network_geometry`, `test_optional_accounts_collection_settings_and_audit`, `core/tests/test_database.py`. | Shared Department schema and initial migration dependency. |
| BE-02 #2 | Four Platform catalogs, management callback, active references, historical reads and unique active names. | `test_catalog_is_shared_and_only_manager_writes`, `test_historical_list_values_are_readable_but_cannot_be_selected`, `test_partial_update_revalidates_unchanged_references`. | Production authorization adapter supplied by security owner. |
| BE-03 #3 | Measurement CRUD, all four required links, optional configuration and accounts, validation and archival. | `test_linked_crud_archival_and_dependencies`, `test_required_relationships_and_non_integer_ids`, `test_collection_settings_validate_named_fields`. | Shared API/security contract acceptance. |
| BE-04 #4 | Device CRUD, Department/type validation, WGS84 Point and logical deletion. | `test_linked_crud_archival_and_dependencies`, `test_network_geometry_validation_and_bbox`, `test_measurement_waits_for_concurrent_device_archive`. | Shared API/security contract acceptance. |
| BE-05 #5 | Network CRUD, three geometry kinds, multiple identifiers, external-system uniqueness, optional model IDs and archival. | `test_identifiers_are_unique_per_external_system_across_elements`, `test_database_rejects_duplicate_active_external_identifiers`, `test_network_model_identifiers_are_persisted_and_searchable`, `test_archived_identifiers_remain_stored_and_can_be_reused`. | Shared API contract acceptance. |
| BE-06 #6 | Native/linked search, active identifier search, exact filters, stable sorting, pagination and Department scope. | `test_search_sorting_filters_and_pagination`, `test_identifier_search_uses_active_values_and_keeps_department_scope`, `test_authorization_scopes_detail_search_create_and_relations`. | Frontend controls and production scope adapter integration. |
| BE-07 #7 | Workbook structure, fields, relationships, settings, duplicates, row errors and whole-workbook rollback. | `test_import_links_all_sheets_and_api_can_read_result`, `test_import_invalid_late_row_rolls_back_all_changes`, `test_import_duplicate_identifiers_reports_row_and_rolls_back`, `test_generated_example_workbook_imports_all_three_domains`. | Client workbook columns and duplicate/retry policy approval under ARCH-01. |
| BE-08 #8 | Archive fields, preserved rows and relationships, dependency conflicts and concurrent-parent protection. | `test_linked_crud_archival_and_dependencies`, `test_external_identifier_updates_preserve_history`, `test_measurement_waits_for_concurrent_catalog_archive`. | Shared audit/Department model review. |

## Integration workflows verified

1. Create a Device and Network Element, create a Measurement with both parents and the shared type/unit, read and update the linked metadata, reject dependent-parent deletion, then archive the Measurement and parents.
2. Generate a linked three-sheet example workbook, upload it through the actual import API and read back all three domains and the external identifier.
3. Reject an invalid late workbook row and a duplicate external identifier; confirm no partial Device, Network Element, Measurement or identifier remains.
4. Search native and linked fields and active external identifiers, filter and page results, and confirm another Department's records remain invisible.
5. Hold an archive transaction while a Measurement creation competes; verify creation waits and then rejects the inactive reference.
6. Compete for one external identifier from two Departments. Verify the unique index chooses one writer and the other receives a 400 field error, or a 400 Excel row error with rollback, rather than a server error.

FixturePolicy is used only inside tests to supply synthetic access scopes through the production adapter interface. These tests validate backend integration and denial behavior; they do not establish that Chrystaleni's real roles, session login, memberships or API keys have been implemented. React user journeys and client acceptance are separate team validation.

## Final audit refinements

The audit found per-element uniqueness where BE-05 requires rejecting duplicate identifiers in the same external system. Migration 0004 enforces active `(source,value)` uniqueness and the API handles concurrent collisions. It also found that general network search omitted external identifiers. Active sources/values now participate in search without duplicate results or retired/unauthorized matches. The tests above reproduce both defects and their fixes.
