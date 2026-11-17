# Shared Department and authorization handover

Argyris Fellas, reviewed 17 November 2026 after PR #27 merged. This records the implemented metadata adapter boundary and remaining ARCH-01 (#9), SEC-01 through SEC-04 (#10-#13) decisions before shared deployment. No production membership model or team approval is invented.

## Proposed Department decision for review

Use one Department model for metadata and security. The current branch supplies `local_departments.Department` with a unique name and positive integer primary key, selected by `METADATA_DEPARTMENT_MODEL`. The proposed first integration is to reuse this Department table and let the security-owned membership app reference it, avoiding a duplicate Department model. This proposal requires Chrystaleni's agreement; it is not recorded as an approved team decision.

If the team instead supplies an existing shared Department model, select its actual `app.Model`, install its app and confirm its first migration before applying metadata migrations to a shared database. All metadata ownership references and the initial migration dependency already use the swappable setting. The backend contract uses positive integer IDs. Changing the setting after migrations are applied does not move existing tables or foreign keys.

The current source does not contain a production User-Department assignment model. Django's existing `AUTH_USER_MODEL` remains the user/audit identity. Real multiple-Department assignments and role membership belong to the security implementation. No replacement User, Role or API-key model is introduced in PR #27.

## Adapter interface ready for integration

Set `METADATA_ACCESS_POLICY` to the actual security adapter class when it is supplied. Its instance methods are:

```python
readable_department_ids(request)       # iterable of integer IDs
writable_department_ids(request)       # iterable of integer IDs
can_manage_controlled_lists(request)   # boolean
```

Return IDs, for example a tuple or `values_list("department_id", flat=True)`, rather than membership/model objects. The adapter derives these decisions from the authenticated identity, real active memberships and agreed roles. Request body/query parameters do not grant access. Authentication and any API-key identity are supplied by the shared DRF authentication layer.

The default `metadata.access.NoAccessPolicy` returns no Department IDs and denies catalog management, including for authenticated superusers. It stays configured until the real adapter is supplied. `FixturePolicy` is confined to automated tests and is not a production authorization implementation.

The Platform Department is the shared catalog owner. Confirm its real persistent ID and set `METADATA_PLATFORM_DEPARTMENT_ID`; fixture ID 1 is an example for an empty local demo database. Do not load demo fixtures into a shared database as a way to create production identities or permissions.

## Role and API-key acceptance still required

The current metadata layer enforces adapter outputs; production roles and memberships are not implemented here.

| Requirement | Required security-owned mapping |
| --- | --- |
| Viewer | Read/search authorized Departments; no metadata/catalog writes |
| Editor | Read and create/update/archive/import in authorized Departments |
| Department Administrator | Editor permissions plus the specifically agreed administration/shared-list grants |
| System Administrator | Agreed platform-wide Department and administration scope through the adapter |
| Memberships | One Role per User and multiple authorized Departments; inactive/revoked assignments excluded |
| API key | Authenticated principal scoped to the key's single Department; empty writable scope and no catalog-management grant |

Do not derive a key's scope from the owner's broader memberships or administrator role. Agree which existing resources are key-readable, including the Measurement `data_collection_config` field referenced by SEC-04; no separate configuration endpoint is introduced.

Invalid, expired or revoked keys must return the required 401. Authenticator ordering/challenge handling must preserve that result alongside current session authentication, whose anonymous denial is 403. Login/logout, CSRF bootstrap, timeout, key issuance/hash storage/expiry/revocation and the actual shared model belong to Chrystaleni's existing security work.

PR #31 requires explicit valid Platform configuration instead of silently assuming Department 1. Configuration must identify the existing approved shared catalog owner. PR #32 supplies the identifier replacement upgrade path; use the [PR #32 database runbook](https://github.com/chrystaleni/sensor-metadata-platform/blob/28e223fcb449c2f556f30d6351e9dd1070593084/docs/development/argyris-database.md) for each starting history and backup/rollback prerequisites.

The [current frontend compatibility audit](pr27-integration-review.md#frontend-compatibility-audit) reviews `Frontend` at `43f109f`. Its upload now includes a CSRF helper, but still uses the wrong Department key and success/error shapes. The accepted multipart name is `department`, and a successful import returns 201 with `created` counts. Antri should correct those exact mappings rather than request a second backend contract.

## Implemented HTTP behavior

| Request | Implemented response |
| --- | --- |
| Unauthenticated metadata request with current SessionAuthentication | 403; authenticated session writes also require CSRF. Other authenticators may use 401. |
| Read within readable Department scope | 200 for an active record. |
| Update/deactivate a readable record without write permission | 403 with stored rows/audit fields unchanged. |
| Detail/update/deactivate outside both permitted scopes | 404 without disclosing the record. |
| Create/import without target-Department write permission | 403 before persistence. |
| Cross-Department parent relationship | 400 field validation; composite database foreign keys also protect Measurement parents. |
| Catalog write without the management callback grant | 403. |
| Deactivate a record with active dependents | 409. |
| Incomplete nested external identifier, including PATCH | 400 with the missing field; the whole request preserves stored data. |

Normal lists/search use readable Department scope and exclude inactive records. A successful write still requires a writable scope grant. No frontend filtering is used for access enforcement. The exact [API methods, fields, examples and workbook format](argyris-api-examples.md) are implemented and ready for ARCH-01 acceptance; client workbook approval is not claimed.

## Concrete acceptance with the shared security implementation

Once the team supplies actual models/adapter, use two Departments and users with writer, reader and unrelated-Department access:

1. Verify that a real multi-Department assignment produces the expected integer read/write ID sets, with revoked/inactive access excluded.
2. Run all three domains through authorized create/read/update/archive and confirm audit attribution uses the authenticated user.
3. Give a user read access without write permission; GET must succeed and PATCH/DELETE must return 403 with unchanged data.
4. Query another Department's records by ID, search and filters. Detail mutations return 404 and normal results omit those records.
5. Reject cross-Department Measurement parents, unauthorized imports and catalog writes, preserving database state.
6. Import the generated linked workbook using approved catalog IDs and an authorized Department. An invalid row must roll back the full workbook.
7. Exercise the actual login/CSRF and API-key mechanisms, and then run the React workflows against the accepted API contract.

These checks supplement the [backend regression suite](pr27-json-parser.md#local-validation-and-re-review), which already tests the callback boundary using synthetic scopes, 400/403/404/409 behavior, PostGIS integrity, rollback and concurrent writes. They do not imply that production security or React end-to-end integration has been implemented by this contribution.

## Remaining acceptance owner

Chrystaleni must confirm the Department model/migration dependency, actual membership-to-role mapping, adapter import path, Platform Department ID and API/workbook contract. The team's review process still requires the appropriate independent approval. PR #27 already supplies the merged metadata backend; the current follow-ups and real security/frontend integration require their own review. No shared migration or approval on another person's behalf is performed.
