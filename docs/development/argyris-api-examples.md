# Backend API and Excel guide

Argyris Fellas, reviewed 14 November 2026. This documents the implementation in PR #27 for the shared API contract review in ARCH-01. All examples use synthetic data.

## Authentication and ownership

The prefix is `/api/v1/`. Requests use the team's existing DRF authentication. Session-authenticated writes must include Django's CSRF token. The current default policy grants no metadata access. Chrystaleni supplies the adapter described in [the handover](argyris-backend.md); no separate login or role system is introduced here.

`department` is required on creation and fixed afterward. Only IDs in the adapter's permitted Departments can be used. The four catalog resources belong to `METADATA_PLATFORM_DEPARTMENT_ID` and are shared. Normal list and detail queries exclude archived records.

Following SEC-03 (#12), an authenticated user who can read a record's Department but cannot write it receives 403 for update/deactivation. Records outside both the readable and writable Department scopes remain hidden with 404. Denied operations preserve the record and its audit/history fields. The [shared integration handover](pr27-shared-integration.md) identifies the Department and adapter decisions needed before a shared migration.

## Collections

| Resource | Required creation fields | Other supported fields |
| --- | --- | --- |
| `physical-devices/` | `department`, `name`, `device_type` | `description`, `location` |
| `network-elements/` | `department`, `name`, `element_type` | `description`, `geometry`, `external_identifiers`, `dma_model_id`, `strategic_model_id` |
| `measurements/` | `department`, `name`, `physical_device`, `network_element`, `measurement_type`, `measurement_unit` | `description`, `customer_account`, `meter_account`, `data_collection_config` |
| `measurement-types/`, `physical-device-types/`, `network-element-types/` | `name` | `description` |
| `measurement-units/` | `name` | `description`, `symbol` |

Collections accept GET and POST. Detail routes `{id}/` accept GET, PUT, PATCH and DELETE. Responses include `id`, `department`, `name`, `description`, `created_at`, `updated_at`, `created_by`, `updated_by` and `is_active`. Actor IDs and timestamps are assigned by the backend.

## Linked create, read and update

After the shared security layer grants write access to Department 2, and catalog IDs 1 exist, POST `/physical-devices/` with:

```json
{"department":2,"name":"Station A","device_type":1,"location":{"type":"Point","coordinates":[33.36,35.15]}}
```

POST `/network-elements/` with:

```json
{"department":2,"name":"Site A","element_type":1,"geometry":{"type":"Point","coordinates":[33.36,35.15]},"external_identifiers":[{"source":"DEMO","value":"SITE-101"}],"dma_model_id":"DMA-1"}
```

Use the returned IDs as `physical_device` and `network_element` when posting `/measurements/`:

```json
{"department":2,"name":"Outside temperature","physical_device":1,"network_element":1,"measurement_type":1,"measurement_unit":1,"customer_account":"CUSTOMER-1","meter_account":"METER-1","data_collection_config":{"protocol":"https","endpoint":"https://example.invalid/metadata","source_identifier":"TEMP-1","extra_settings":{"interval_seconds":60}}}
```

The IDs above are illustrative, not assumed generated values. Successful creation returns 201. GET the returned detail route to read a record. PATCH `/measurements/{id}/` with `{"description":"Roof sensor"}` returns the updated record with status 200. The collection configuration stores metadata; the backend does not connect to its endpoint or collect time series.

Geometry is two-dimensional WGS84 GeoJSON with longitude first. Devices accept Point; Network Elements accept Point, LineString or Polygon. Optional geometry accepts null. Invalid coordinate ranges and invalid polygon rings return 400.

## Search, filters and paging

```text
GET /api/v1/measurements/?search=temperature&physical_device=1&department=2&ordering=-created_at&page_size=25
GET /api/v1/physical-devices/?device_type=1&bbox=33,35,34,36
GET /api/v1/network-elements/?search=SITE-101&element_type=1
GET /api/v1/network-elements/?identifier=SITE-101
```

Search includes native names, descriptions and relevant linked type/record names. Measurement search also includes customer and meter accounts. Network search also includes DMA/Strategic IDs and active external identifier sources and values. Multiple search terms must all match somewhere on the record. Exact ID filters use the relationship field names from the table, plus `department`. `identifier` matches an active external identifier's exact value.

Ordering supports `id`, `name`, `created_at`, `updated_at`, and a minus sign for descending order. The backend adds ID ordering to break ties. Default page size is 25, maximum 100. Lists return `{"count":2,"next":null,"previous":null,"results":[...]}`. Department scope applies before search and filtering.

Read an archived controlled-list value with `?include_inactive=true`. It has `is_active=false` and cannot be selected for a new or updated record.

## Logical deletion

DELETE a Measurement before deleting its Device or Network Element. Successful deletion returns 204 and preserves the stored record, relationships, timestamp and actor. An active dependent record produces 409. A later normal GET of the archived detail returns 404. No user-facing endpoint permanently deletes metadata.

External identifier updates replace the active list when supplied, retain unchanged pair IDs and archive removals. Within the selected Department, an active `(source,value)` may belong to only one Network Element. Another Department may use the same pair independently, even if the caller can read both Departments. Duplicate validation queries only the target Department, so a hidden Department's claim does not change API or Excel success/failure. The same value in a different source is allowed. Strings are compared exactly; source codes should use a consistent spelling.

Identifier ownership is derived from the Network Element. The nested request/response shape remains `{id,source,value}` (id is read-only); callers do not select a separate Department per identifier. The [Department identifier handover](pr27-identifier-departments.md) records migration 0005 and the privacy/concurrency regressions.

### PATCH external identifiers

Each supplied identifier must include both `source` and `value`, including on PATCH. Omitting the entire `external_identifiers` field leaves the stored list unchanged. Explicitly sending `[]` archives all active identifiers. These rules do not make unrelated record fields required on PATCH.

For example, PATCH `/api/v1/network-elements/7/` with:

```json
{"external_identifiers":[{"source":"ERP","value":"SITE-101"}]}
```

returns 200 with the updated Network Element. An illustrative response is:

```json
{"id":7,"department":2,"name":"Site A","description":"","created_at":"2026-11-14T08:00:00Z","updated_at":"2026-11-14T08:05:00Z","created_by":2,"updated_by":2,"is_active":true,"element_type":1,"geometry":null,"external_identifiers":[{"id":12,"source":"ERP","value":"SITE-101"}],"dma_model_id":"","strategic_model_id":""}
```

Sending `{"external_identifiers":[{"source":"ERP"}]}` returns 400:

```json
{"external_identifiers":{"0":{"value":["This field is required."]}}}
```

Missing `source` produces the corresponding `source` error. DRF 3.18 encodes item positions as object keys such as `"0"`, matching the submitted list index. An invalid item rejects the entire request: identifiers, archive/audit fields and unrelated record changes remain unchanged. A valid item elsewhere in the same list is not partially saved.

## Excel workflow

From `backend/`, generate the implemented template or the linked example:

```sh
python manage.py metadata_workbook metadata-template.xlsx
python manage.py metadata_workbook metadata-example.xlsx --example
```

The command refuses to replace a file unless `--force` is supplied. The example expects the optional `demo_departments` and `demo_catalog` fixtures in an empty local database, with catalog IDs 1. Load those fixtures only into an isolated demo database. Real imports use the actual approved catalog IDs and an authorized Department.

POST multipart fields `department=2` and `file=metadata-example.xlsx` to `/api/v1/imports/excel/` using the team's authenticated session and CSRF handling. The first row contains exact header names; the [handover's sheet table](argyris-backend.md#proposed-workbook-format) lists all supported columns. `@station-a` and `@site-a` refer to rows from the same workbook; numeric IDs refer to existing active parents in the selected Department. Geometry, identifiers and collection settings use JSON text cells.

Limits are 5 MiB compressed, 25 MiB expanded, 200 ZIP entries and 2,000 data rows per sheet. Formulas, Excel errors, macros, unknown sheets, duplicate headers and unresolvable references are rejected. Files use literal cells. Blank optional cells are omitted.

A successful import returns 201:

```json
{"created":{"Physical Devices":1,"Network Elements":1,"Measurements":1}}
```

An invalid row returns 400 and rolls back the entire workbook:

```json
{"errors":[{"sheet":"Measurements","row":3,"errors":{"measurement_type":["Invalid pk \"999\" - object does not exist."]}}]}
```

File-level errors use null `sheet` and `row`. Duplicate external identifiers are rejected using the same rule as the API, including concurrent collisions. Imports create new records; there is no upsert or automatic retry deduplication. Repeating the example while its identifier is active fails and rolls back.

Missing/invalid multipart fields (including an empty upload) use ordinary field-keyed 400 errors before workbook processing. Corrupt ZIP, XML or DEFLATE content returns the unreadable-workbook 400 file error. The worksheet row-position limit rejects row 2002, including blank gaps after the header.

## Error handling

| Status | Meaning |
| --- | --- |
| 400 | Invalid field, geometry, relationship or workbook. Inspect field messages or row errors. |
| 403 | No authenticated session, CSRF failure or insufficient write/catalog permission, including a read-only user's update/deactivation attempt. |
| 404 | Missing, inactive or out-of-scope detail, or invalid pagination page. |
| 405 | HTTP method unsupported at the requested collection/detail URL. |
| 409 | Active dependents prevent logical deletion. |
| 415 | Unsupported request media type, including JSON at the multipart-only Excel endpoint. |

The shared authentication owner may add authenticators that return 401 for unauthenticated requests. Frontend clients should handle the agreed authentication contract rather than rely on one authenticator's status.

The [individual error catalog](../testing/backend-error-catalog.md) maps 310 error cases to executable test IDs, expected input/status/message and integrity checks. Its companion JSON records complete observed error bodies. It also documents accepted boundary inputs, pagination fallbacks, read-only audit fields and the remaining production authorization boundary.
