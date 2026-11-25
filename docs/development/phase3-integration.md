# Local Phase 3 integration

This guide describes `integration/phase3-platform`, a local integration branch. It does not claim that its changes are published on GitHub or merged into main.

The backend change from FastAPI to Django was requested by KIOS CoE; DRF supplies the REST API. The existing Organisation, Department and metadata migrations are retained. The only additional schema is the API key table; existing Department primary keys are never reassigned.

## Installation and startup

Use Docker Desktop/Engine and Compose, or Python 3.13, Node 24 and PostgreSQL/PostGIS with GDAL/GEOS/PROJ. Install `backend/requirements.txt` into a virtualenv and run `npm ci` in `frontend`.

Copy `.env.example` to `.env`. Set unique database credentials and a unique `DJANGO_SECRET_KEY` before using Compose (the backend runs with DEBUG false and rejects the insecure fallback). Never commit `.env`. The Docker build excludes environment files and virtualenvs.

Fresh installation only:

```sh
docker compose build
docker compose up -d db
docker compose run --rm backend python manage.py check
docker compose run --rm backend python manage.py migrate --noinput
docker compose run --rm backend python manage.py provision_platform_department
```

Set `METADATA_PLATFORM_DEPARTMENT_ID` in `.env` to the exact ID printed by the command. Missing, malformed, non-positive and out-of-range IDs are unconfigured; no ID 1 default exists. The owner must belong to the unique Platform Organisation, and all shared catalogs must agree with that owner. Provisioning is a separate explicit operator command.

For an existing database, **do not follow the fresh-install migration command blindly**. Take a verified backup, inspect existing migration history and identifier collisions, and follow [the Organisation backfill runbook](department-organisation-backfill.md) and [identifier upgrade runbook](pr27-identifier-departments.md). Supply only an approved mapping:

```sh
docker compose run --rm -e DEPARTMENT_ORGANISATION_BACKFILL="$(cat approved-backfill.json)" backend python manage.py migrate --noinput
```

The mapping is deliberately not forwarded as an empty default by Compose. Existing Departments require an approved manifest. Cross-Department active identifier duplicates are supported by the replacement migration; same-Department active duplicates fail atomically and require a separately approved data remediation. No automatic deletion, renaming, archiving or reassignment is performed.

Create approved business Organisations and Departments through the existing operator model workflow before assigning memberships; this branch does not claim a browser Organisation administration API. Select the business Department for operational metadata. The Platform Department is the shared catalog owner.

After the complete permission and migration suite passes in disposable PostGIS, explicitly select the real adapter:

```dotenv
METADATA_ACCESS_POLICY=platform_security.access.DepartmentAccessPolicy
```

The default remains `metadata.access.NoAccessPolicy`; signing in alone does not grant metadata permissions. Configure a user explicitly:

```sh
docker compose run --rm backend python manage.py configure_platform_user operator --create --role SYSTEM_ADMIN
# Existing users: omit --create. --department <existing-id> can be repeated.
```

Passwords are entered interactively and never passed on the command line. The command validates Department existence, adds requested memberships, preserves existing memberships and changes the role only as explicitly requested. It does not set Django `is_staff`/`is_superuser`. Department/Organisation creation and membership removal currently remain operator tasks, not browser administration features.

```sh
docker compose up -d backend frontend
```

Open `http://localhost:8080`. React requests `/api/v1` on the same origin; nginx proxies to Django. Backend startup never runs migrations. The existing database volume is preserved. `/health/` is liveness; `/ready/` checks database connectivity and pending migrations without applying them. Frontend startup waits for backend readiness. Stop with `docker compose down` without the volumes flag.

For host development: start the database, run Django on 8000, then `npm run dev` in frontend. Vite proxies `/api` to Django. `VITE_PROXY_TARGET` changes its target; `VITE_API_BASE_URL` defaults to `/api/v1`. Use a same-origin deployment; direct cross-origin cookie access is not automatically configured. Set secure cookies and trusted HTTPS origins behind a reviewed TLS proxy. The provided Compose setup is a local deployment, not a completed internet production hardening profile. Address-based login throttling ignores untrusted forwarded headers; peers sharing a proxy/NAT share a failure budget until trusted client-address handling is configured at the serving boundary.

## Sessions, roles and Department scope

See [session authentication](session-authentication.md) for the existing CSRF/login/logout/session contracts and expiry/throttling semantics. `GET /api/v1/auth/context/` adds current role, readable Departments with Organisation codes, per-Department `writable`, and capability flags. It never exposes other users' memberships and respects the selected access policy. Responses are non-cacheable. The original `/session/` contract remains unchanged.

React restores sessions after refresh, bootstraps CSRF before login/logout, includes cookies and sends the rotated cookie token on writes. It checks session status periodically and after data reloads. Expiration removes protected UI; server-side permissions apply immediately, even before the next browser poll. Role/scope changes remount the workspace to clear stale local state. No session tokens, passwords or metadata are persisted to localStorage.

| Explicit role | Metadata reads | Metadata writes/import | Shared catalogs | API key management |
|---|---|---|---|---|
| No role / inactive / anonymous | Denied | Denied | Denied | Denied |
| Viewer | Member Departments | Denied | Read through authorized scope | Denied |
| Editor | Member Departments | Member Departments | Read | Denied |
| Department Administrator | Member Departments | Member Departments | Read | Member Departments |
| System Administrator | All Departments | All Departments | Manage | All Departments |

Multi-Department membership is supported. Cross-Organisation access derives from explicit Department membership; there is no implicit Organisation-wide grant. Merely being Django staff or superuser does not grant a platform role. UI controls reflect capabilities but never replace backend authorization.

## Read-only API keys (Issue #13)

Management is session-authenticated and CSRF-protected:

- `POST /api/v1/api-keys/`: `{ "name": "SCADA", "department": <authorized-id>, "expires_at": "<future ISO timestamp>" }`. Expiration defaults to 90 days. Returns 201 with metadata and `key` **once**.
- `GET /api/v1/api-keys/` and `GET /api/v1/api-keys/<id>/`: metadata only, never digest or raw key. Lists are DRF-paginated; optional `department` limits scope.
- `DELETE /api/v1/api-keys/<id>/`: revokes (204), without deleting the audit record.

Measurement collection configuration is stored as its own `DataCollectionConfiguration` entity (one per Measurement, migration `metadata.0006`, which copies existing values). It is read through `GET /api/v1/measurements/<id>/configuration/` (Phase 2 design, Table 4; 404 when absent) and still appears as `data_collection_config` in the Measurement response and in create/update/import payloads, so existing clients are unaffected. If a creation response is lost, revoke that key and issue a new one; the server cannot recover the raw secret.

Send `X-API-Key: smk_<prefix>.<secret>` to metadata GET endpoints. Keys use cryptographically random 256-bit secrets and random prefixes; only SHA-256 digests are stored. Comparison is constant-time. A supplied key is authoritative even when browser cookies are present. Write methods are rejected with 403, key management cannot use keys, and the Department policy intersects key scope with the issuer's current authority. Expired/revoked/invalid keys, disabled/deleted issuers, loss of administrator role/membership or default-deny policy return generic 401. Cross-Department details/explicit scope requests are hidden with 404. Revocation applies to subsequent authentication checks; a read already in flight may complete.

The React API Keys page supports creation, one-time display/hide and revocation. No key is persisted by the UI. Never log key headers, creation responses or browser traces from a real deployment. Disposable E2E traces may contain generated test-only keys.

## Metadata workflows

The existing [metadata API contract](argyris-api-examples.md) remains authoritative. Operational creates carry the selected authorized Department; PATCH preserves ownership. Relationship dropdowns restrict operational parents to that Department. Shared catalogs remain Platform-owned and require System Administrator writes. An otherwise authorized user receives 403 if the Platform owner is invalid; default-deny users retain empty lists/hidden details.

GIS uses GeoJSON Point/LineString/Polygon with WGS84 `[longitude, latitude]`. Form and map validation share the geometry validator. Resource-qualified map keys prevent Device/Network ID collisions. Leaflet ships with the application; OpenStreetMap basemap tiles still need internet access.

CSV escapes formula-leading cells. XLSX writes typed strings rather than formulas. Export retrieves paginated authorized records, with an explicit 100,000-record safety limit. Preload uses the same limit, loads beyond 1,000 records, reports per-resource failures and retains successful resources. This is client-side preload, not streaming large-dataset support. Search cancels and ignores stale responses. Mutation/import refreshes the dashboard and GIS.

Import accepts the backend's three-sheet XLSX contract with `file` and selected `department` multipart fields. Errors include sheet/row/field details. Use `python manage.py metadata_workbook <path.xlsx>` for a template. The client's own workbook layout (`Measurements`, `NetworkElements`, `Physical_devices`) is also accepted. **Download Excel workbook** exports a Department in that client layout, so the file can be edited and imported again (#49); the import refuses rows whose `Department` column names a different existing Department. Single-table XLSX/CSV exports are flat reports and are not import files. Archived (soft-deleted) records are hidden from Viewers and Editors; Department and System Administrators can list them with `include_archived=true` and use `POST …/{id}/restore/` and `DELETE …/{id}/purge/` (#48).

## Validation and current limitation

Run frontend checks with `npm test -- --run`, `npm run lint`, `npm run build`. Backend: `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python -m pytest -v` against disposable PostGIS only.

The isolated runner never uses `.env` database credentials, never mounts an existing database volume, and removes only its newly created container. It generates random credentials, waits for final TCP readiness before extension initialization, creates the PostGIS test template, runs fresh migrations, the complete backend suite, frontend checks and real Playwright workflows. It retains logs/XML/traces under `/tmp/sensor-phase3-validation.*`.

From this integration clone, with Docker Desktop available:

```sh
npm --prefix frontend ci
npm --prefix frontend exec -- playwright install chromium
PYTHON=/absolute/path/to/a/backend-virtualenv/bin/python bash scripts/validate_disposable.sh
```

The default ARM64 image is the previously downloaded `ghcr.io/cargosense/postgis:17-3.5-alpine`; override `POSTGIS_TEST_IMAGE` for another already-downloaded, approved image. The script uses temporary storage and a random loopback host port. Its final E2E fixture is explicitly gated to `sensor_validation_*`; it does not load demo fixtures into a real database.

On 25 November 2026 the complete runner passed on a developer machine: system checks, migrations and drift check, the full PostGIS backend suite, frontend tests, lint, build and the Playwright browser workflows. The CI workflow runs the same checks on every push.

If your local `.env` sets `METADATA_PLATFORM_DEPARTMENT_ID`, unset it for the runner: the script relies on that variable being absent while it seeds the disposable database, and `python-dotenv` would otherwise read it from `.env`.
