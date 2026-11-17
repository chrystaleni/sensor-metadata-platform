# Shared Department and authorization handover

Argyris Fellas, 14 November 2026. This is the concrete backend integration proposal for PR #27, ARCH-01 (#9) and SEC-03 (#12). It records implemented behavior and the remaining architecture/security-owner decisions before a shared migration or merge.

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

Chrystaleni must confirm the Department model/migration dependency, actual membership-to-role mapping, adapter import path, Platform Department ID and API/workbook contract. The protected repository also requires an approving teammate review. PR #27 supplies the tested backend side and this reviewable proposal; no shared migration, merge or approval on another person's behalf is performed.
