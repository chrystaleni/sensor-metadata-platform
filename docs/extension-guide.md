# Extension guide

How the code is organised and where to make the most common changes. Run the checks in [Checks before a pull request](#checks-before-a-pull-request) for every change.

## Where things live

| Area | Location | What it holds |
|---|---|---|
| Metadata | `backend/metadata/` | `models.py` (records, shared lists, identifiers, collection configuration), `serializers.py` (validation), `views.py` (API, archive/restore/purge), `filters.py` (search, filters, pagination), `imports.py` (platform template import), `client_format.py` (client workbook layout), `exports.py` (client-layout export), `access.py` (access policy interface) |
| Security | `backend/platform_security/` | `access.py` (`DepartmentAccessPolicy`: roles and Department scope), `views.py` (login/logout/session), `admin_api.py` (users, Organisations, Departments), `login_throttle.py`, `session_expiry.py` |
| API keys | `backend/api_keys/` | key model, `X-API-Key` authentication, management API |
| Departments | `backend/local_departments/` | Organisation and Department models |
| Platform | `backend/core/`, `backend/config/` | health/ready checks, OpenAPI (`/api/v1/openapi.json`, `/api/v1/docs/`), settings |
| Frontend | `frontend/src/feall/` | `backendModel.js` (form fields per resource), `App.jsx` (pages, tables, forms), one file per screen (`ExcelPage`, `GisMap`, `ApiKeys`, `UsersAdmin`, `Settings`, `Dashboard`) |
| Navigation | `frontend/src/fe02/navigation.js` | sidebar pages (`NAV_ITEMS`) |

Access rules are never enforced by the frontend alone. The frontend hides buttons, and the backend decides.

## Add a field to a record

Example: a `serial_number` on Physical Devices.

1. **Model:** add the field to `PhysicalDevice` in `backend/metadata/models.py` (`blank=True` if it is optional), then run `python manage.py makemigrations metadata`. Review the migration: it must not change existing data.
2. **Serializer:** add it to `PhysicalDeviceSerializer.Meta.fields` in `serializers.py`, plus any validation (`validate_serial_number`).
3. **Search** (optional): add it to `search_fields` on `PhysicalDeviceViewSet` in `views.py`.
4. **Import and export** (optional):
   - Platform template: add it to the optional columns of `SHEETS["Physical Devices"]` in `imports.py`.
   - Client layout: add the column to `CLIENT_SHEETS` and `FIELD_TO_COLUMN` and read it in `resolve_client_records` (`client_format.py`), then write it in `exports.py`.
5. **Form:** add `['serial_number','Serial number']` to `resources['physical-devices'].fields` in `frontend/src/feall/backendModel.js`. The third item sets the input type (`textarea`, `json`, `geo`, `number`, or a related resource such as `physical-device-types` for a dropdown), and `true` as the fourth item makes the field required.
6. **Table column** (optional): add it to `visibleColumns` in `App.jsx`.
7. **Tests:** the API (create, edit, clear the field), import/export if changed, and the form.

## Add a value list (controlled list)

Shared lists inherit from `ControlledListEntry` (`models.py`), which provides Platform ownership, unique active names and archiving. For a new list:
1. Add the model and its serializer and view (copy `MeasurementUnit`, its serializer and `MeasurementUnitViewSet`), and set `dependent_relations` to the reverse relation(s) that must block archiving.
2. Register the route in `metadata/urls.py`.
3. Add it to `resources` in `backendModel.js`. The first three entries are the operational records and the rest are shared lists (`catalogKeys`), so it appears on **Controlled Lists** automatically.

## Change what a role may do

All role and Department decisions are in `platform_security/access.py` (`DepartmentAccessPolicy`):

| Method | Decides |
|---|---|
| `readable_department_ids` / `writable_department_ids` | which Departments a user or API key may read or change |
| `can_manage_controlled_lists` | who adds, edits, archives, restores and deletes shared list entries |
| `archive_manager_department_ids` | who sees, restores and permanently deletes archived records |

User administration rules (who may create, edit, reactivate and delete users, Organisations and Departments) are in `admin_api.py`. The frontend reads the permissions from `/api/v1/auth/context/`, built in `platform_security/context.py`. Add a flag there when a new screen needs one. New policy methods should also get a safe default (deny) in `metadata/access.py` `NoAccessPolicy`.

## Add a page

1. Create the screen in `frontend/src/feall/`, for example `Reports.jsx`, with a test next to it.
2. Add `{ id: 'reports', label: 'Reports', icon: '…' }` to `NAV_ITEMS` in `fe02/navigation.js`.
3. Render it in `Workspace` in `App.jsx` (`page.id==='reports'?<Reports …/>:…`).

## Add an API endpoint

Prefer a DRF view or a `@action` on an existing viewset, because then authentication (session and `X-API-Key`), CSRF and the OpenAPI schema work automatically. Inherit `DepartmentScope` (in `metadata/views.py`) for Department checks. Return `404` for records outside the caller's Departments and `403` for missing role permissions (Phase 2, §1.4.3). Writes go through `transaction.atomic` and `lock_metadata_write(department_id)`.

## Checks before a pull request

```sh
cd backend && python manage.py check && python manage.py makemigrations --check --dry-run && python -m pytest -q
cd frontend && npm test -- --run && npm run lint && npm run build
```

Backend tests need PostgreSQL/PostGIS (see the README). For the full browser test run `scripts/validate_disposable.sh` (see the [integration guide](development/phase3-integration.md)).
