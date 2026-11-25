# User guide

This guide explains how to use the Sensor Metadata Management Platform in the browser. For installation see the [Quick start in the README](../README.md#quick-start-run-locally-with-docker). For external systems see the [API guide](development/argyris-api-examples.md) and the interactive documentation at `/api/v1/docs/` (sign in first).

## Signing in

Open the platform (for a local installation <http://localhost:8080>) and sign in with the username and password your administrator gave you. After five failed attempts within 15 minutes, sign-in is paused for a while. A session ends after 30 minutes without activity and after 8 hours in total.

To sign out, open the **profile menu** (your initials, top right) and choose **Log out**, or use **Settings → Log out**.

## Departments and roles

Records belong to a **Department** (for example *Nicosia* or *Limassol*). You only see the Departments you are a member of; System Administrators see all of them. Choose the Department you work in from the **profile menu**. Every page, import and export then uses that Department.

| Role | What you can do |
|---|---|
| **Viewer** | View, search and export records in your Departments. |
| **Editor** | Everything a Viewer can do, plus create, edit, archive and import records in your Departments. |
| **Department Administrator** | Everything an Editor can do, plus see/restore/delete archived records, manage the shared lists, and manage the users and API keys of your Departments. |
| **System Administrator** | Everything, in every Department, plus Organisations and Departments, and reactivating or deleting users. |

Buttons you are not allowed to use are not shown.

## Pages

### Dashboard
Totals, breakdowns by type, how many records have a map position, and the most recent changes in the selected Department.

### Measurements, Physical Devices, Network Elements
Each page lists the records of the selected Department.

- **Search** looks in names, descriptions and linked fields (for example a measurement's device or type, a network element's identifiers or DMA/Strategic model IDs). **Sort by** orders the list.
- **Filters** narrow the list by related records: Measurements by physical device, network element, measurement type and unit; Physical Devices by device type; Network Elements by element type. **Clear filters** resets them.
- **View** shows every field of a record. For a device or network element with a location, **Show on map** opens the GIS Map zoomed to it.
- **+ Add** and **Edit** open a form. Fields marked `*` are required. A measurement must have a physical device, a network element, a measurement type and a unit.
  - Locations and geometries are GeoJSON in WGS84, longitude first, for example `{"type":"Point","coordinates":[33.36,35.15]}`. Network elements may also be `LineString` or `Polygon`.
  - *Communication parameters* and *Collection config* are JSON objects, for example `{"IP":"10.0.0.1"}`.
  - If a value is not accepted, the field is outlined in red with the reason underneath. Correct it and press **Save** again.
- **Archive** hides a record without deleting it. A record that other active records still use cannot be archived; archive those first (for example the measurements of a device).

**Archived records (Department and System Administrators):** archived records appear in the lists as faded rows with the status **Archived** and two actions:
- **Restore** brings the record back. A measurement can only be restored after its device and network element are active again.
- **Delete** removes it permanently. Only archived records that nothing else uses can be deleted, and this cannot be undone.

### GIS Map
Shows the physical devices and network elements of the selected Department that have a location. Click a record in the list to zoom to it. **Search** filters the records by name, identifier or type. **Show** limits the map to one kind, and **Include inactive** adds archived records. Records without a valid location are listed under the map. The basemap needs an internet connection.

### Controlled Lists
The shared lists used by every Department: measurement types, measurement units, device types and network element types. Everyone can view them. Department and System Administrators can add, edit, archive, restore and delete entries. An entry that records still use cannot be archived or deleted. Records that use an archived entry keep showing its name, marked *(archived)*; it can no longer be chosen for new records.

### Excel Import / Export
**Import** (Editors and above) adds many records at once to the selected Department. The page shows which Department will receive them. Two workbook layouts are accepted:

1. **The client layout**, with sheets `Measurements`, `NetworkElements` and `Physical_devices` and the client's column names (`MeasurementId`, `NetworkElementId`, `Device_id`, …). Types and units are given by name. A name that is missing from the shared lists is added automatically when a Department or System Administrator imports; otherwise the row is rejected. If the `Department` column names a different existing Department than the selected one, the import is refused, so records cannot land in the wrong Department.
2. **The platform template**, with sheets `Physical Devices`, `Network Elements` and `Measurements`. Get it with **Download template**; required columns are bold.

An import is all-or-nothing. If any row is invalid, nothing is saved and every problem is listed with its sheet, row and column. Importing the same workbook twice is refused because its identifiers already exist.

**Export:**
- **Download Excel workbook** saves the selected Department in the client layout. You can edit that file and import it again.
- **Export a single table** saves one list (XLSX or CSV) with all its API fields, for reading only.

### API Keys (Department and System Administrators)
Creates read-only keys that let an external system read one Department. Each key is shown **only once** when it is created, so copy it then. By default a key expires after 90 days; choose another date, or **No expiration** for a key that works until it is revoked. **Revoke** stops a key immediately, including an expired one. System Administrators can **Delete** keys that are revoked or expired. See [Using an API key](#using-an-api-key).

### Administration (Department and System Administrators)
Create users, change their role and Departments with **Edit**, **Deactivate** users who should no longer sign in, and (System Administrators) **Reset password**, **Reactivate** or **Delete** users. Department Administrators manage only Viewers and Editors of their own Departments. A deleted user's records stay, without their name.

### Settings
Your account and role, **Change password**, your **default Department** (stored in this browser), and **Log out**. Department Administrators also see their Departments. System Administrators also manage **Organisations and Departments**: add them, and delete empty ones. Platform can never be deleted.

## Using an API key

Send the key in the `X-API-Key` header. A key only reads the Department it was created for:

```sh
curl -H "X-API-Key: smk_..." "http://localhost:8080/api/v1/measurements/?department=2"
curl -H "X-API-Key: smk_..." "http://localhost:8080/api/v1/measurements/15/configuration/"
```

| Answer | Meaning |
|---|---|
| `200` | The data. |
| `401` | The key is wrong, expired or revoked. |
| `403` / `404` | The record is outside the key's Department, or the key tried to change something (keys are read-only). |

## Messages you may see

| Message | What to do |
|---|---|
| *Invalid username or password.* | Check both; the message never says which one was wrong. |
| *Too many login attempts. Try again later.* | Wait and try again. |
| *Archive the active records that reference this record first.* | Archive the records that use it (for example its measurements). |
| *This row belongs to Department 'X', but you are importing into 'Y'.* | Choose Department X in the profile menu and import again. |
| *An active identifier with this source and value already exists.* | The record was already imported or created; use the existing one. |
