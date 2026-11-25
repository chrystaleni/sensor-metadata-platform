# Release notes

## Phase 3 — November 2026

The first complete release of the Sensor Metadata Management Platform: a React/Vite frontend, a Django REST Framework backend and PostgreSQL/PostGIS, run together with Docker Compose. The backend uses Django instead of the FastAPI named in the Phase 2 design, at the client's request.

### Metadata
- Measurements, Physical Devices and Network Elements per Department, with required relationships: a measurement always has a device, a network element, a type and a unit (#27).
- Network elements store external identifiers, DMA and Strategic model IDs, network area, elevation and address. Physical devices store communication parameters. Measurements store customer and meter accounts and a separate data collection configuration (#27, #37, #38).
- PostGIS locations and geometries in WGS84: points for devices; points, lines and polygons for network elements (#27).
- Search across native and linked fields, sorting and pagination (#27).
- Shared controlled lists (measurement types and units, device and element types) owned by the Platform Department (#27, #33).
- Logical deletion (**Archive**): a record that active records still use cannot be archived (#27). Department and System Administrators see archived records, and can restore them or delete them permanently (#48).

### Access and security
- Session sign-in and sign-out with login throttling, idle and absolute session timeouts, and CSRF protection.
- Four roles (Viewer, Editor, Department Administrator, System Administrator), membership in several Departments, and Department isolation, where records of other Departments return 404.
- Read-only, Department-scoped API keys in the `X-API-Key` header. A key is shown once and stored as a hash, and it can expire or be revoked (#34).
- User administration: create, deactivate, and reset passwords (System Administrators) (#37, #43). System Administrators also reactivate and permanently delete users, delete empty Departments and Organisations, and delete revoked or expired API keys (#51).
- Department Administrators manage the shared lists (#50), as in Phase 2 Table 3.

### Excel
- All-or-nothing import with row-level errors for the platform template and for the client's own workbook layout (#27, #37).
- Excel workbook export of a Department in the client layout, which can be edited and imported again. The import refuses rows whose `Department` column names a different Department (#49).
- Single-table XLSX and CSV export.

### Interface
- Dashboard, record pages, GIS map with Greek basemap labels, Controlled Lists, Excel Import/Export, API Keys, Administration and Settings, with actions shown according to role (#30, #35, #36 Greek map labels, #37 administration screens).
- Log out from Settings (#44), a "Save" button with no technical wording (#45), a status badge that stays on one line (#42), and a map that returns to its default view for an empty Department (#49).
- OpenAPI documentation at `/api/v1/docs/` after sign-in.

### Upgrade notes
- The backend never migrates automatically. Run `python manage.py migrate` after every update.
- Set `METADATA_PLATFORM_DEPARTMENT_ID` and `METADATA_ACCESS_POLICY=platform_security.access.DepartmentAccessPolicy` in `.env` (see the README).

### Known limitations
- Sign-in endpoints (`/api/v1/auth/…`) are documented in [session-authentication.md](development/session-authentication.md), not in the OpenAPI page.
- The map basemap needs an internet connection.
- Behind the bundled nginx, the address recorded for a request is the proxy's address.
- `scripts/validate_disposable.sh` reads a developer's local `.env`. If that file sets `METADATA_PLATFORM_DEPARTMENT_ID`, the seed step fails; run the script with that variable unset.

### In review
Open pull requests at the time of writing: table filters (#52), editing a user's role and Departments (#53), new fields in the import template (#54), template download (#55), login events in the application log (#56), names of archived list values (#57), "Show on map" and map search (#58), optional API-key expiration (#59), highlighted form errors (#60). Update these notes as they merge.
