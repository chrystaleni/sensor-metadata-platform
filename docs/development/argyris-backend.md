# Backend contribution by Argyris Fellas

Recorded on 13 November 2026. This branch implements the backend areas of BE-01 through BE-08 against the existing Django project and PostGIS configuration.

The backend contribution is complete for review under BE-01 through BE-08. The shared Department schema and access adapter, the final API contract under ARCH-01 (#9), and workbook-column approval remain team integration decisions before merge and deployment.

## Delivery contents

- [API examples and import instructions](argyris-api-examples.md)
- [Database and migration handover](argyris-database.md)
- [Acceptance criteria and validation evidence](../testing/argyris-backend-validation.md)
- [AI tool selection, specifications and development log](argyris-ai-development-log.md)

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

METADATA_PLATFORM_DEPARTMENT_ID selects the built-in Platform Department. The example value is 1. The optional demo_departments and demo_catalog fixtures are intended for an empty local database and use IDs 1 and 2.

Authentication, real role rules, membership and API keys remain integration dependencies on SEC-01 through SEC-04. The code's callbacks are an implementation proposal for that integration.

## Proposed API

The prefix is /api/v1/. Collections are measurements/, physical-devices/, network-elements/, measurement-types/, measurement-units/, physical-device-types/ and network-element-types/. POST creates a record. GET lists records. GET, PUT, PATCH and DELETE operate on {id}/. DELETE returns 204 after archiving, or 409 if active dependent records exist. Default queries exclude archived records.

Requests use integer relationship IDs. The department ID is required on create and cannot be reassigned. Every Measurement requires physical_device, network_element, measurement_type and measurement_unit. Relationship selections must be active and in the selected Department or the Platform shared list as appropriate.

Responses include id, department, name, description, created_at, updated_at, created_by, updated_by and is_active. List responses contain count, next, previous and results. Validation errors use DRF's field-keyed messages. Authenticated users receive 403 for unauthorized creation. Out-of-scope detail records return 404.

List parameters include search, ordering, page, page_size and relationship field names. Ordering supports id, name, created_at and updated_at, with a minus sign for descending order. Page size defaults to 25 and is limited to 100. Device and network lists support bbox=west,south,east,north with increasing WGS84 coordinates. Network lists also support identifier for an exact active external identifier value.

Controlled-list reads can include archived values using include_inactive=true. Such values are returned with is_active=false and cannot be chosen on metadata writes.

Network element external_identifiers accepts objects with source and value. An update containing this list replaces the active list, preserving unchanged pairs and archiving removals. Active `(source, value)` pairs are unique across Network Elements, including across Departments, as required by BE-05's external-system duplicate rule. Comparisons use exact strings. An archived pair remains in history and may be reused. Duplicate responses expose no other record or Department details. General text search includes active identifier sources and values; retired identifiers are excluded.

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

The integrated official project was checked with Python 3.12.14, Django 5.2.19, PostgreSQL 16.15, PostGIS 3.4.6 and GDAL 3.12.4.

- Django system check reported no issues.
- All migrations were applied to the disposable database.
- makemigrations --check --dry-run reported no changes.
- python -m pytest -v reported 36 passed and 9 passed subtests, including the original database and health checks.
- Tests exercise Excel rollback, department scope, optional account/model identifiers, inactive controlled values, audit attribution, concurrent parent/catalog archival and concurrent identifier collisions across Departments.
- The generated example workbook was imported through the actual API and linked all three domains successfully.

Run the same checks from backend/ using the documented PostGIS environment. The existing GitHub Actions workflow also checks for missing migrations.

## AI development evidence

Argyris Fellas used Codex to construct the three-domain Django backend and then inspect the actual repository and BE-01 through BE-08 acceptance criteria. Inspection identified account/model identifier fields and named collection settings to add before integration. The final audit corrected external-system identifier uniqueness and added active-identifier search, concurrent-collision handling and an executable workbook example. The implementation was refined, migrated and tested in the official repository structure. The linked development log records prompts, changes and observed validation. Team review of the shared schema, authorization interface and final contract remains pending.
