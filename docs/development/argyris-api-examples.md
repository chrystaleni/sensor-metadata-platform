# Backend API and Excel guide

Argyris Fellas, reviewed 17 November 2026 against published main `2f97a90c6d1bef8301aff68c03b5b0b9130e3d65` (merged PR #27). PR #31 (`aa743dd6`) and PR #32 (`e4fa5de5`) remain separate follow-ups at this review point. This is the implemented metadata contract for ARCH-01 (#9); examples use synthetic data.

## Authentication and ownership

The prefix is `/api/v1/`, with trailing slashes. Published settings use DRF `SessionAuthentication` and `IsAuthenticated`. Session-authenticated writes require Django's CSRF token, normally supplied as `X-CSRFToken` with the session credentials. No login/logout or explicit CSRF-bootstrap URL is registered in the inspected project. Chrystaleni supplies the agreed authentication flow and the adapter described in [the handover](argyris-backend.md). The default `metadata.access.NoAccessPolicy` grants no metadata access.

For operational records, `department` is required on creation and fixed afterward. Only IDs in the adapter's permitted Departments can be used. Catalog `department` is read-only and assigned by the server. The four catalog resources belong to `METADATA_PLATFORM_DEPARTMENT_ID` and are shared. Normal list and detail queries exclude archived records.

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

## Exact methods and response schemas

The collection paths in the resource table are relative to `/api/v1/`. Each of the seven resources exposes this same method set:

| URL | Method | Request | Successful response |
| --- | --- | --- | --- |
| `/api/v1/{resource}/` | GET | Query parameters; no request body needed | 200 paginated object |
| `/api/v1/{resource}/` | POST | Required creation fields plus optional fields | 201 complete created object |
| `/api/v1/{resource}/{id}/` | GET | No request body needed | 200 complete object |
| `/api/v1/{resource}/{id}/` | PUT | `name` and all required domain relationship fields | 200 complete updated object |
| `/api/v1/{resource}/{id}/` | PATCH | Only supplied changes; existing relationships are revalidated | 200 complete updated object |
| `/api/v1/{resource}/{id}/` | DELETE | No request body needed | 204 empty body |

An operational PUT does not require `department` again. If supplied during PUT/PATCH, it must equal the existing Department. Required relationship fields are `device_type` for Devices; `element_type` for Network Elements; and `physical_device`, `network_element`, `measurement_type`, `measurement_unit` for Measurements. Catalog PUT requires `name`.

PATCH does not make omitted unrelated fields required. However, an unchanged relationship to an archived or no-longer-permitted record produces 400 until corrected. Omitted optional fields are preserved during update, including PUT; use an allowed explicit value such as `null` or an empty string/list to clear a field.

Complete object schemas consist of these common fields plus every field in the appropriate domain table:

| Common response field | Type | Client write behavior |
| --- | --- | --- |
| `id` | Integer primary key | Read-only, generated by server |
| `department` | Integer primary key | Operational creation selects it; fixed afterward. Catalog ownership is server-assigned |
| `name` | Non-empty string, maximum 120 characters | Required POST/PUT |
| `description` | String, empty allowed; null rejected | Optional, empty on creation when omitted |
| `created_at`, `updated_at` | ISO 8601 datetime strings | Read-only |
| `created_by`, `updated_by` | User ID or null | Read-only, assigned by server |
| `is_active` | Boolean | Read-only; archive with DELETE |

| Resource | Additional response/request fields |
| --- | --- |
| Physical Device | `device_type`: required catalog ID; `location`: optional GeoJSON Point or null |
| Network Element | `element_type`: required catalog ID; `geometry`: optional GeoJSON Point/LineString/Polygon or null; `external_identifiers`: optional array; `dma_model_id` and `strategic_model_id`: optional strings up to 255 characters |
| Measurement | Four required relationship IDs listed above; `customer_account` and `meter_account`: optional strings up to 255 characters; `data_collection_config`: optional JSON object or null |
| Measurement Type / Physical Device Type / Network Element Type | Common fields only |
| Measurement Unit | Common fields plus `symbol`: optional string up to 24 characters |

IDs are serialized as numbers; relationship labels are not expanded. Input ID fields are positive integers up to `2**63 - 1`. Related operational records must be active and in the selected Department. Related catalog values must be active in the configured Platform Department. Operational names are not required to be unique. Active catalog names are unique case-insensitively within their catalog/Department.

Optional string fields default to an empty string on creation; optional geometry/configuration fields default to null; omitted identifiers default to an empty array. Undeclared fields and read-only input fields are ignored by the normal serializers. Do not rely on a 400 response to catch a misspelled DTO property.

The list response is:

```json
{"count":0,"next":null,"previous":null,"results":[]}
```

`count` is the total matching authorized count before pagination. `next` and `previous` are page URLs or null. Each `results` item is a complete object. Single-object responses have no `results` wrapper. `deleted_at` and `deleted_by` are retained in the database but not exposed here.

### Fully qualified resource inventory

| Collection URL | Detail URL | Domain |
| --- | --- | --- |
| `/api/v1/measurements/` | `/api/v1/measurements/{id}/` | Operational |
| `/api/v1/physical-devices/` | `/api/v1/physical-devices/{id}/` | Operational |
| `/api/v1/network-elements/` | `/api/v1/network-elements/{id}/` | Operational |
| `/api/v1/measurement-types/` | `/api/v1/measurement-types/{id}/` | Shared catalog |
| `/api/v1/measurement-units/` | `/api/v1/measurement-units/{id}/` | Shared catalog |
| `/api/v1/physical-device-types/` | `/api/v1/physical-device-types/{id}/` | Shared catalog |
| `/api/v1/network-element-types/` | `/api/v1/network-element-types/{id}/` | Shared catalog |

The additional metadata endpoint is multipart-only POST `/api/v1/imports/excel/`. There is no registered standalone endpoint for external identifiers, collection configuration, export, restore, dashboard aggregation, Users or Departments. `/api/v1/` itself is not an API-root route. Standard DRF HEAD/OPTIONS behavior is available where supported. The separate unauthenticated `GET /health/` returns `{"status":"ok"}`.

## Detailed query contract

Filters apply to list operations after Department scoping. Detail access uses its own permission-scoped lookup rather than the list filters.

| Resource | Exact positive-ID filters | Additional query support |
| --- | --- | --- |
| Measurements | `department`, `physical_device`, `network_element`, `measurement_type`, `measurement_unit` | `search`, `ordering`, `page`, `page_size` |
| Physical Devices | `department`, `device_type` | Common queries and `bbox` |
| Network Elements | `department`, `element_type` | Common queries, `bbox` and `identifier` |
| Controlled lists | None | Common queries and read-only `include_inactive` |

All resources search `name` and `description`. Device search includes the device-type name. Measurement search includes account strings and linked Device, Network Element, Measurement Type and Measurement Unit names. Network search includes the element-type name, DMA/Strategic IDs and active external identifier sources/values. Unit search also includes `symbol`. Matching is case-insensitive; multiple terms must each match somewhere on the record.

`identifier` is a non-blank string up to 255 characters and matches an active identifier's exact value; there is no separate exact-source query parameter.

`bbox=west,south,east,north` selects spatial intersections. Coordinates must satisfy `-180 <= west < east <= 180` and `-90 <= south < north <= 90`. Geometry-less records do not intersect the box.

`ordering` accepts `id`, `name`, `created_at` and `updated_at`, with a leading minus for descending. Default is `id`; a missing ID tie-break is added. Unrecognized ordering is ignored/falls back to the valid/default ordering. Fields such as `type` and `externalId` are not ordering keys.

`page` starts at 1; an invalid/out-of-range page returns 404. `page_size` defaults to 25 and is capped at 100. Invalid, zero and negative sizes use the default.

`include_inactive=true` also makes archived catalog detail records readable; writes still require active records. It does not expose archived operational records. Unknown query names do not define additional filtering behavior: `status`, `active` and `type` are not supported contract filters.

## Geometry and collection settings details

GeoJSON fields accept geometry objects, not Feature/FeatureCollection, WKT, root latitude/longitude fields or a `crs` member. Coordinates contain exactly two numeric, non-boolean values ordered longitude/latitude. Devices accept Point only. Network Elements accept Point, LineString with at least two positions, or Polygon with closed rings of at least four positions; empty/invalid geometries are rejected. Range/validity checks are API validation. PostGIS enforces the field SRID/type and the Network Element geometry-type constraint.

Each supplied external identifier requires both non-blank strings: `source` up to 120 and `value` up to 255 characters. The list has a maximum of 100 items. Its `id` is read-only and its Department is derived from the Network Element.

`data_collection_config` accepts an object or null. Known optional properties are:

| Property | Validation |
| --- | --- |
| `protocol` | String up to 50 characters; empty allowed |
| `endpoint` | String up to 2048 characters; empty allowed |
| `source_identifier` | String up to 255 characters; empty allowed |
| `extra_settings` | JSON object |

Additional configuration keys are retained. There is no protocol enum or URL-format validator. Null characters, invalid UTF-8 JSON strings and non-finite JSON numbers are rejected. This field stores configuration metadata only.

## Exact workbook columns

Headers and sheet names are case-sensitive. A workbook may contain a subset of these sheets, with at least one metadata row overall:

| Sheet | Required columns | Optional columns |
| --- | --- | --- |
| `Physical Devices` | `name`, `device_type` | `ref`, `description`, `location` |
| `Network Elements` | `name`, `element_type` | `ref`, `description`, `geometry`, `external_identifiers`, `dma_model_id`, `strategic_model_id` |
| `Measurements` | `name`, `physical_device`, `network_element`, `measurement_type`, `measurement_unit` | `description`, `data_collection_config`, `customer_account`, `meter_account` |

The multipart `department` applies to every created operational row. Do not add a Department column to the sheets. `ref` is a unique per-sheet label of 1-64 characters matching `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`; a relationship cell uses `@label`. Device/Network references are resolved in fixed processing order: Physical Devices, Network Elements, Measurements. Catalog cells use active Platform IDs.

Success counts include the sheets supplied. Rejected workbook rows use `errors[].errors` with the serializer's nested field errors. Missing or invalid multipart fields use top-level field-keyed errors instead, for example:

```json
{"department":["This field is required."]}
```

A frontend error mapper must handle both envelopes, including nested indexed identifier errors. A successful import should refresh affected API lists; repeating a request is not an idempotent retry.

## Current permissions and pending security integration

| Operation | Current adapter requirement |
| --- | --- |
| Operational list/retrieve | Authenticated request and readable Department |
| Operational POST/import | Authenticated request and writable selected Department |
| Operational PUT/PATCH/DELETE | Record visible to readable or writable scope, then writable Department required |
| Catalog read | Authenticated request with any readable Department, or `can_manage_controlled_lists=True`; rows restricted to Platform |
| Catalog write | Authenticated request, configured Platform and `can_manage_controlled_lists=True` |

Authenticated default-deny users receive empty lists, 404 details and forbidden writes. Readable-but-not-writable operational details return 403 for writes; records outside both scopes stay hidden with 404. Django `is_superuser` alone does not bypass the adapter.

Published main defaults `METADATA_PLATFORM_DEPARTMENT_ID` to 1. PR #31 replaces that fallback with explicit configuration: missing, invalid, non-positive or out-of-range input becomes unconfigured, so shared-list access is not silently assigned to a customer's Department. A valid setting must identify the approved existing Platform Department; configuration does not create or move catalog rows.

Relevant environment settings are:

| Setting | Boundary |
| --- | --- |
| `METADATA_DEPARTMENT_MODEL` | Defaults to `local_departments.Department`. Shared model changes require an agreed migration strategy |
| `METADATA_PLATFORM_DEPARTMENT_ID` | Existing approved Platform Department ID; use explicit configuration with PR #31 |
| `METADATA_ACCESS_POLICY` | Defaults to `metadata.access.NoAccessPolicy`. Chrystaleni supplies the real adapter class |

The adapter methods are `readable_department_ids(request)`, `writable_department_ids(request)` and `can_manage_controlled_lists(request)`. Real User memberships, the four roles, login/logout, timeout and API-key authentication remain the security integration in Issues #10-#13; the fixture-policy tests do not prove those implementations exist.

API keys are planned as `X-API-Key`, one Department, read-only, with expiry/revocation and hashed storage. Their Department scope must come from the key, not broader permissions of its owner. Invalid/expired/revoked keys must return the agreed 401, requiring appropriate authenticator ordering/challenge behavior. The current session-only configuration returns 403 for anonymous requests.

The security owner must confirm which existing resources keys can read and whether Issue #13's configuration reference means the implemented Measurement `data_collection_config` field. This guide introduces no new endpoint.

For React on a separate origin, agree either a same-origin proxy or the required credentialed CORS/CSRF configuration. `credentials: 'include'` alone supplies neither Department selection nor a CSRF token. Production authentication integration must reuse Chrystaleni's existing work.

## Error handling

| Status | Meaning |
| --- | --- |
| 400 | Invalid field, geometry, relationship or workbook. Inspect field messages or row errors. |
| 403 | No authenticated session, CSRF failure or insufficient write/catalog permission, including a read-only user's update/deactivation attempt. |
| 404 | Missing, inactive or out-of-scope detail, or invalid pagination page. |
| 405 | HTTP method unsupported at the requested collection/detail URL. |
| 409 | Active dependents prevent logical deletion. |
| 415 | Unsupported request media type, including JSON at the multipart-only Excel endpoint. |

Deeply nested JSON rejected during parsing returns HTTP 400 with `{"detail":"JSON parse error."}`. The default Form/MultiPart parsers remain enabled for metadata, while Excel keeps its explicit multipart-only parser. Invalid parsing or identifier validation does not persist partial metadata or identifier changes.

The shared authentication owner may add authenticators that return 401 for unauthenticated requests. Frontend clients should handle the agreed authentication contract rather than rely on one authenticator's status.

The [individual error catalog](../testing/backend-error-catalog.md) maps 310 error cases to executable test IDs, expected input/status/message and integrity checks. Its companion JSON records complete observed error bodies. It also documents accepted boundary inputs, pagination fallbacks, read-only audit fields and the remaining production authorization boundary.
