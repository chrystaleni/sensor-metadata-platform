# Backend contribution by Argyris Fellas

Recorded on 13 November and reviewed on 17 November 2026. PR #27's BE-01 through BE-08 metadata implementation is merged into main at `2f97a90c`. PRs #31 and #32 remain separate follow-ups at this review point.

The metadata features are implemented. The shared Department schema and access adapter, the final API contract under ARCH-01 (#9), and workbook-column approval remain team integration decisions before shared deployment.

## Delivery contents

- [API examples and import instructions](argyris-api-examples.md)
- [Database and migration handover](argyris-database.md)
- [Acceptance criteria and validation evidence](../testing/argyris-backend-validation.md)
- [AI tool selection, specifications and development log](argyris-ai-development-log.md)
- [Shared Department and authorization integration handover](pr27-shared-integration.md)

Use the repository README to install the backend and start PostGIS. Then run `python manage.py makemigrations --check --dry-run` and `python -m pytest -v` from `backend/`. An authenticated session alone grants no metadata access with the default policy; the shared adapter below must supply the user's Department scope.

## Implemented behavior

- Department-owned Measurements, Physical Devices and Network Elements, with migrations and database constraints for same-Department Measurement links.
- Platform-owned Measurement Types, Measurement Units, Physical Device Types and Network Element Types.
- WGS84 GeoJSON validation and PostGIS storage for Points on devices and Points, LineStrings or Polygons on network elements.
- Required Measurement relationships, optional customer_account and meter_account strings, and collection configuration with protocol, endpoint, source_identifier and extra_settings.
- Network elements with optional dma_model_id and strategic_model_id strings and multiple external identifiers.
- REST create, retrieve and update operations, logical deletion, dependency conflicts, creator/updater attribution and archive history.
- Search, exact relationship filters, spatial filtering, stable ordering and pagination.
- Atomic Excel import across all three domains with row errors and workbook references.

## Shared integration boundary

METADATA_DEPARTMENT_MODEL selects the Department model. The current default local_departments.Department is a swappable fixture model because the base repository has no shared Department or membership models. Chrystaleni should review this boundary and the initial migration dependency before any team database applies these migrations.

METADATA_ACCESS_POLICY selects the team's authorization adapter. It supplies readable_department_ids(request), writable_department_ids(request), and can_manage_controlled_lists(request). The default NoAccessPolicy denies metadata access. The APIs use DRF SessionAuthentication and Django's existing user model. The test-only FixturePolicy supplies synthetic department access for automated tests.

`METADATA_PLATFORM_DEPARTMENT_ID` selects the approved existing Platform Department. Published main still defaults it to 1; PR #31 requires explicit configuration and treats missing, invalid, non-positive or out-of-range values as unconfigured. With that change present, add the agreed integer ID to the repository-root `.env`. This setting neither creates a Department nor reassigns existing catalogs.

The optional `demo_departments` and `demo_catalog` fixtures use IDs 1 and 2 only in an empty isolated demo database. Their Platform ID 1 is not evidence of the shared deployment's correct ID. An unconfigured Platform produces empty catalog reads and prevents catalog writes/selections rather than silently using a customer's Department. The real authorization adapter is still required.

See the [API guide](argyris-api-examples.md) for current/pending authentication behavior and the [PR #32 database runbook](https://github.com/chrystaleni/sensor-metadata-platform/blob/28e223fcb449c2f556f30d6351e9dd1070593084/docs/development/argyris-database.md) for source-revision and shared-model prerequisites.

Authentication, real role rules, membership and API keys remain integration dependencies on SEC-01 through SEC-04. The code's callbacks are an implementation proposal for that integration.

## Proposed API

The prefix is /api/v1/. Collections are measurements/, physical-devices/, network-elements/, measurement-types/, measurement-units/, physical-device-types/ and network-element-types/. POST creates a record. GET lists records. GET, PUT, PATCH and DELETE operate on {id}/. DELETE returns 204 after archiving, or 409 if active dependent records exist. Default queries exclude archived records.

Requests use integer relationship IDs. An operational record's department ID is required on create and cannot be reassigned; controlled-list ownership is server-assigned. Every Measurement requires physical_device, network_element, measurement_type and measurement_unit. Relationship selections must be active and in the selected Department or the Platform shared list as appropriate.

Responses include id, department, name, description, created_at, updated_at, created_by, updated_by and is_active. List responses contain count, next, previous and results. Validation errors use DRF's field-keyed messages. Authenticated users receive 403 for unauthorized creation. Out-of-scope detail records return 404.

An update/deactivation of a readable record without write permission returns 403, in accordance with SEC-03. A record outside both permitted scopes remains 404. Every supplied external identifier requires source and value even during PATCH; invalid items return 400 without changing stored data. Omitting the list preserves it and an explicit empty list archives its active entries.

List parameters include search, ordering, page, page_size and relationship field names. Ordering supports id, name, created_at and updated_at, with a minus sign for descending order. Page size defaults to 25 and is limited to 100. Device and network lists support bbox=west,south,east,north with increasing WGS84 coordinates. Network lists also support identifier for an exact active external identifier value.

Controlled-list reads can include archived values using include_inactive=true. Such values are returned with is_active=false and cannot be chosen on metadata writes.

Network element external_identifiers accepts objects with source and value. An update containing this list replaces the active list, preserving unchanged pairs and archiving removals. Active `(source, value)` pairs are unique across Network Elements within the selected Department. The same pair is allowed in another Department, and duplicate validation does not inspect other Departments. Migration 0005 adds and backfills ownership, enforces matching parent ownership and replaces the global constraint; existing migrations are unchanged. Comparisons use exact strings. An archived pair remains in history and may be reused. General text search includes active identifier sources and values; retired identifiers are excluded. See the [Department identifier handover](pr27-identifier-departments.md) for the clarified rule and tests.

## Proposed workbook format

POST /api/v1/imports/excel/ accepts multipart fields department and file. The upload must be an .xlsx workbook, at most 5 MiB and 2,000 data rows per sheet. Cells contain literal values and the header names are exact.

| Sheet | Required columns | Optional columns |
| --- | --- | --- |
| Physical Devices | name, device_type | ref, description, location |
| Network Elements | name, element_type | ref, description, geometry, external_identifiers, dma_model_id, strategic_model_id |
| Measurements | name, physical_device, network_element, measurement_type, measurement_unit | description, data_collection_config, customer_account, meter_account |

Geometry, external identifiers and data collection configuration use JSON text cells. Use an existing integer ID for relationships or @ref for a device or network element created in the same workbook. Reference labels are unique per sheet. Controlled-list IDs must already exist in the Platform Department.

Any invalid row rejects the entire import. A successful response returns 201 with created counts by sheet. A rejected workbook returns 400 with errors containing sheet, Excel row and field errors. Each successful upload creates a new batch. The current implementation has no automatic retry deduplication.

Generate the exact implemented headers with `python manage.py metadata_workbook metadata-template.xlsx`. Add `--example` for synthetic linked rows using controlled-list IDs 1 from the optional demo fixtures. The example is intended for an empty local database, and repeat imports of its active external identifier are rejected. These files describe the implemented format for ARCH-01 review; no approval of a client workbook template is implied.

## Validation performed

The historical 15 November integrated project checks used Python 3.13.18, Django 5.2.19, PostgreSQL 16.15, PostGIS 3.4.6 and GDAL 3.12.4.

- Django system check reported no issues.
- All migrations were applied to the disposable database.
- makemigrations --check --dry-run reported no changes.
- python -m pytest -v reported 383 passed and 18 passed subtests, including the previous 359 tests and 24 Department-identifier regressions.
- Tests exercise Excel rollback, Department scope, optional account/model identifiers, inactive controlled values, audit attribution and concurrent parent/catalog archival. Identifier tests reject same-Department collisions, permit independent claims across Departments and verify migration backfill/downgrade integrity.
- The generated example workbook was imported through the actual API and linked all three domains successfully.
- Read-only update/deactivation returns 403 for all three domains without changing stored data; cross-Department access still returns 404.

Run the same checks from backend/ using the documented PostGIS environment. The existing GitHub Actions workflow also checks for missing migrations.

The [individual error catalog](../testing/backend-error-catalog.md) documents 310 separately executable error cases with input, HTTP/error expectations and preservation assertions. The other ten new tests cover accepted boundaries, pagination fallbacks, audit fields, workbook generation and a real session/CSRF exchange. A corrupt compressed workbook regression exposed an uncaught zlib error; the existing workbook handler now returns its standard 400 file error. No model, migration, frontend or CI workflow changed in this error audit.

### 17 November verification

Published main `2f97a90c` passes 387 tests and 18 subtests. PR #31 `aa743dd6` passes 397 tests and 20 subtests; PR #32 `e4fa5de5` passes 393 tests and 18 subtests in their completed GitHub Actions runs.

A separate local verification copied all 82 main files after checking their Git blob hashes, overlaid the eight verified PR #31/#32 changed files, and ran against a new disposable PostgreSQL 16.15/PostGIS 3.4.6 cluster using Python 3.13.18 and Django 5.2.19. Main passed 387 tests plus 18 subtests; the combined snapshot passed 403 tests plus 20 subtests, with zero failures/errors/skips. Dependency checks, Django checks, migrations and model/migration consistency passed. The server was stopped after validation. This combined local result is not a GitHub Actions result for a merged revision.

Completed CI evidence: [main](https://github.com/chrystaleni/sensor-metadata-platform/actions/runs/44108479433), [PR #31](https://github.com/chrystaleni/sensor-metadata-platform/actions/runs/44115739167), [PR #32](https://github.com/chrystaleni/sensor-metadata-platform/actions/runs/44134065018).

Real authentication/Organisation integration and frontend end-to-end workflows remain unverified in the published implementation. A green metadata suite does not substitute for those owner-provided components.

## AI development evidence

Argyris Fellas used Codex to construct the three-domain Django backend and then inspect the actual repository and BE-01 through BE-08 acceptance criteria. Inspection identified account/model identifier fields and named collection settings to add before integration. The final audit corrected external-system identifier uniqueness and added active-identifier search, concurrent-collision handling and an executable workbook example. The implementation was refined, migrated and tested in the official repository structure. The linked development log records prompts, changes and observed validation. Team review of the shared schema, authorization interface and final contract remains pending.
