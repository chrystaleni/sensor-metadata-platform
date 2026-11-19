# AI-assisted integration log — 19 November 2026

Work was performed in an independent clone on `integration/phase3-platform`.
The original repository and remote branches were not modified. The clone uses
independent Git objects (`--no-hardlinks`), preserving all original commits.
The original `.git` is read-only under the session filesystem policy; no Unix
permission changes, sudo or security workarounds were used.

## Inputs inspected

- Main: `65d35dee3d4d9370b52a1c47122b419bf57b8955` (reverified remotely).
- Organisation PR #33: `61dfba31e83a47350a9c763e54eac2850eed6dbc`, OPEN.
- Authentication: `b83db60692670cd973045635502bed581de25a73`.
- Frontend PR #30: `2f1a3e24ff9ce16a10551f773611ded58519ebeb`, OPEN.
- GitHub Issue #13: API key requirements; Issue #3: existing Measurement configuration contract.

## Decisions and review

Reused all three existing feature implementations through local merge commits.
Kept the existing Department table, IDs, Organisation backfill approval gate,
Platform identity checks, original metadata replacement migrations and SafeJSONParser.
No existing production migration was rewritten. Added only the API key migration.
NoAccessPolicy remains the default; the real adapter is explicitly enabled only
inside the disposable runner after the preceding backend suite succeeds.

Added key-aware session authentication to prevent a supplied API key borrowing
broader browser privileges. Keys are read-only, Department-scoped, hashed and
revocable, and their issuer's current authority is rechecked. Preserved the
existing four-role semantics and added explicit operator provisioning.

Reviewed frontend request races, partial preload failures, full pagination,
formula-leading CSV cells, GIS resource identities, shared geometry validation,
CSRF/session workflows, capability controls and refresh after import. Leaflet is
bundled locally; external basemap tiles remain an explicit dependency.

Static graph inspection identified that metadata downgrades also unapply the
three dependent security migrations. Updated the historical test assertions to
list those exact migrations, retaining strict checks for unrelated history.
Added database-free checks proving both graph states are equal and identifying
the exact descendants. Actual rollback execution still requires PostGIS.

## Validation boundary

70 frontend tests and 36 database-free backend tests executed successfully.
574 backend tests and three browser workflows collected/discovered successfully;
collection is not execution. Full PostGIS and E2E execution is blocked because
Docker socket access is denied; host PostgreSQL initialization also failed under
shared-memory restrictions. No persistent database was accessed. A failed attempt
to use SQLite for the PostGIS-only test demonstrated its unsupported spatial
operations; it was not treated as a successful integration run.

Updated the existing CI workflow to run a disposable PostGIS/browser validation
and retain test evidence. The new workflow has not run remotely; nothing was pushed.
No test was removed, skipped or marked xfail to conceal a failure. Coverage was
not measured. No claim of production or Phase 3 delivery readiness is made.

## Local implementation commits (before this documentation checkpoint)

```text
b9a94f3 chore(integration): incorporate verified Organisation foundation
a227df8 chore(auth): integrate existing session, membership and role implementation
6922f48 chore(frontend): incorporate reviewed PR 30 implementation
f4c3247 fix(gis): distinguish resource identities without changing database IDs
1b51595 fix(export): neutralize formula-leading CSV cells
66169a3 feat(api): add scoped expiring read-only API keys
9fd7975 feat(auth): expose fail-closed session capability context
c6a235f fix(frontend): load complete resources independently and cancel stale work
1b8d15b feat(frontend): connect sessions and department-scoped metadata workflows
167106c test(migrations): track dependent security restoration explicitly
caa18fa test(api): verify key boundaries and protect management requests
4e307b6 feat(auth): provision explicit roles and existing memberships safely
686a589 fix(frontend): share geometry validation and map Django metadata
bb2446a feat(frontend): manage scoped API keys and clear revoked session scope
ac76824 build(frontend): install bundled maps and browser test tooling
7619629 fix(gis): bundle Leaflet and preserve selected resource identity
42daeb6 feat(docker): run the full app with explicit migrations and readiness
504d121 test(integration): validate real workflows in disposable PostGIS
ec3a65a fix(frontend): include all authorized key-management pages
6aa4a3c test(api): cover scoped external measurement configuration reads
8483eae test(integration): isolate browser configuration from deployment settings
67329d3 test(e2e): exercise department switching and complete relational CRUD
```
