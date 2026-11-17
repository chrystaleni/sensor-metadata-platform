"""Executable error contract: plain data shared by regression tests and docs.

Tokens beginning with $ are resolved to real database fixtures by the tests.
Every case has a stable pytest ID; no HTTP response is mocked.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Case:
    id: str
    group: str
    title: str
    resource: str = "physical-devices"
    method: str = "POST"
    status: int = 400
    path: tuple = ()
    message: str = ""
    changes: dict = field(default_factory=dict)
    query: dict = field(default_factory=dict)
    setup: str = ""
    actor: str = "editor"


OPERATIONS = ("physical-devices", "network-elements", "measurements")
CATALOGS = {
    "physical-device-types": "device_type",
    "network-element-types": "element_type",
    "measurement-types": "measurement_type",
    "measurement-units": "measurement_unit",
}
RELATIONSHIPS = {
    "physical-devices": ("device_type",),
    "network-elements": ("element_type",),
    "measurements": ("physical_device", "network_element", "measurement_type", "measurement_unit"),
}


def api_cases():
    cases = []
    for resource in (*OPERATIONS, *CATALOGS):
        actor = "catalog-manager" if resource in CATALOGS else "editor"
        for suffix, value, message in (
            ("missing", "$omit", "This field is required."),
            ("blank", " ", "This field may not be blank."),
            ("null", None, "This field may not be null."),
            ("long", "n" * 121, "no more than 120 characters"),
        ):
            cases.append(Case(f"FIELD-{resource}-name-{suffix}", "Required fields and limits",
                              f"{resource}: name {suffix}", resource, actor=actor,
                              changes={"name": value}, path=("name", 0), message=message))
        cases.append(Case(f"FIELD-{resource}-description-null", "Required fields and limits",
                          f"{resource}: null description", resource, actor=actor,
                          changes={"description": None}, path=("description", 0),
                          message="This field may not be null."))
    for resource in OPERATIONS:
        for suffix, value, message in (
            ("missing", "$omit", "This field is required."),
            ("null", None, "This field may not be null."),
            ("text", "north", "A valid integer is required."),
            ("zero", 0, "greater than or equal to 1"),
            ("overflow", 2**63, "less than or equal to 9223372036854775807"),
        ):
            cases.append(Case(f"DEPT-{resource}-{suffix}", "Department selection",
                              f"{resource}: department {suffix}", resource,
                              changes={"department": value}, path=("department", 0), message=message))
        cases.append(Case(f"DEPT-{resource}-immutable", "Department selection",
                          f"{resource}: PATCH cannot move department", resource, "PATCH",
                          changes={"department": 3}, path=("department", 0),
                          message="The department is fixed when the record is created.", actor="multi"))
    for resource, fields in RELATIONSHIPS.items():
        for name in fields:
            for suffix, value, message in (
                ("missing", "$omit", "This field is required."),
                ("null", None, "This field may not be null."),
                ("fraction", 1.5, "A valid integer is required."),
                ("zero", 0, "object does not exist"),
                ("overflow", 2**63, "object does not exist"),
                ("absent", 99999999, "object does not exist"),
                ("scope", f"$other_{name}", "object does not exist"),
            ):
                cases.append(Case(f"REL-{resource}-{name}-{suffix}", "Relationships",
                                  f"{resource}: {name} {suffix}", resource,
                                  changes={name: value}, path=(name, 0), message=message))
            cases.append(Case(f"REL-{resource}-{name}-archived", "Relationships",
                              f"{resource}: select archived {name}", resource,
                              setup=f"archive:{name}", path=(name, 0), message="object does not exist"))
            cases.append(Case(f"REL-{resource}-{name}-unchanged-archived", "Relationships",
                              f"{resource}: PATCH rechecks unchanged archived {name}", resource, "PATCH",
                              setup=f"archive:{name}", changes={"name": "Attempted edit"},
                              path=(name, 0), message="Choose an active record in the permitted department."))
    for resource, fields in {
        "network-elements": ("dma_model_id", "strategic_model_id"),
        "measurements": ("customer_account", "meter_account"),
        "measurement-units": ("symbol",),
    }.items():
        for name in fields:
            limit = 24 if name == "symbol" else 255
            for suffix, value, message in (("null", None, "This field may not be null."),
                                           ("long", "x" * (limit + 1), f"no more than {limit} characters")):
                cases.append(Case(f"FIELD-{name}-{suffix}", "Optional field limits",
                                  f"{name}: {suffix}", resource,
                                  actor="catalog-manager" if resource in CATALOGS else "editor",
                                  changes={name: value}, path=(name, 0), message=message))
    for missing in ("source", "value", "both"):
        item = {"source": "ERP", "value": "new"}
        for name in (("source", "value") if missing == "both" else (missing,)):
            item.pop(name)
        for method in ("POST", "PATCH"):
            cases.append(Case(f"EXT-{method}-missing-{missing}", "External identifiers",
                              f"{method}: missing identifier {missing}", "network-elements", method,
                              changes={"external_identifiers": [item]},
                              path=("external_identifiers", 0, "source" if missing == "both" else missing, 0),
                              message="This field is required."))
    for name, limit in (("source", 120), ("value", 255)):
        for suffix, value, message in (("blank", " ", "This field may not be blank."),
                                       ("null", None, "This field may not be null."),
                                       ("long", "x" * (limit + 1), f"no more than {limit} characters")):
            item = {"source": "ERP", "value": "new", name: value}
            cases.append(Case(f"EXT-{name}-{suffix}", "External identifiers",
                              f"Identifier {name}: {suffix}", "network-elements", "PATCH",
                              changes={"external_identifiers": [item]},
                              path=("external_identifiers", 0, name, 0), message=message))
    for suffix, value, path, message in (
        ("null-list", None, ("external_identifiers", 0), "This field may not be null."),
        ("object-not-list", {}, ("external_identifiers", "non_field_errors", 0), "Expected a list"),
        ("scalar-item", ["ERP"], ("external_identifiers", 0, "non_field_errors", 0), "Expected a dictionary"),
        ("too-many", [{"source": "ERP", "value": str(i)} for i in range(101)],
         ("external_identifiers", "non_field_errors", 0), "no more than 100 elements"),
        ("duplicate-in-list", [{"source": "ERP", "value": "new"}] * 2,
         ("external_identifiers", 0), "Each source and value pair must be unique."),
        ("already-claimed", [{"source": "OTHER", "value": "claimed"}],
         ("external_identifiers", 0), "An active identifier with this source and value already exists."),
        ("mixed-incomplete", [{"source": "ERP", "value": "new"}, {"source": "ERP"}],
         ("external_identifiers", 1, "value", 0), "This field is required."),
    ):
        cases.append(Case(f"EXT-{suffix}", "External identifiers", suffix, "network-elements", "PATCH",
                          changes={"external_identifiers": value, "name": "Attempted edit"},
                          path=path, message=message))
    for resource, name in (("physical-devices", "location"), ("network-elements", "geometry")):
        type_message = "Expected WGS84 GeoJSON geometry of type"
        coordinate_message = "Provide valid two-dimensional longitude and latitude coordinates in WGS84."
        values = (
            ("scalar", "POINT(1 2)", type_message),
            ("missing-type", {"coordinates": [1, 2]}, type_message),
            ("unsupported-type", {"type": "MultiPoint", "coordinates": [[1, 2]]}, type_message),
            ("crs", {"type": "Point", "coordinates": [1, 2], "crs": None}, type_message),
            ("missing-coordinates", {"type": "Point"}, coordinate_message),
            ("third-dimension", {"type": "Point", "coordinates": [1, 2, 3]}, coordinate_message),
            ("boolean", {"type": "Point", "coordinates": [True, 2]}, coordinate_message),
            ("text", {"type": "Point", "coordinates": ["1", 2]}, coordinate_message),
            ("longitude", {"type": "Point", "coordinates": [181, 2]}, coordinate_message),
            ("latitude", {"type": "Point", "coordinates": [1, -91]}, coordinate_message),
            ("empty", {"type": "Point", "coordinates": []}, coordinate_message),
        )
        for suffix, value, message in values:
            cases.append(Case(f"GEO-{name}-{suffix}", "Geographic validation", f"{name}: {suffix}",
                              resource, "PATCH", changes={name: value}, path=(name, 0), message=message))
    for suffix, value in (
        ("line-one-point", {"type": "LineString", "coordinates": [[1, 2]]}),
        ("line-repeated-point", {"type": "LineString", "coordinates": [[1, 2], [1, 2]]}),
        ("polygon-empty", {"type": "Polygon", "coordinates": []}),
        ("polygon-short-ring", {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]}),
        ("polygon-unclosed", {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}),
        ("polygon-self-intersection", {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]}),
    ):
        cases.append(Case(f"GEO-{suffix}", "Geographic validation", suffix, "network-elements", "PATCH",
                          changes={"geometry": value}, path=("geometry", 0),
                          message="Provide valid two-dimensional longitude and latitude coordinates in WGS84."))
    for suffix, value, path, message in (
        ("array", [], (), "Expected a JSON object."),
        ("scalar", "https", (), "Expected a JSON object."),
        ("protocol-long", {"protocol": "p" * 51}, ("protocol", 0), "no more than 50 characters"),
        ("endpoint-long", {"endpoint": "e" * 2049}, ("endpoint", 0), "no more than 2048 characters"),
        ("source-long", {"source_identifier": "s" * 256}, ("source_identifier", 0), "no more than 255 characters"),
        ("protocol-object", {"protocol": {}}, ("protocol", 0), "Not a valid string."),
        ("protocol-null", {"protocol": None}, ("protocol", 0), "This field may not be null."),
        ("extra-array", {"extra_settings": []}, ("extra_settings", 0), "Expected a JSON object."),
        ("extra-null", {"extra_settings": None}, ("extra_settings", 0), "This field may not be null."),
        ("null-in-value", {"custom": ["bad\x00value"]}, (), "JSON strings cannot contain null characters."),
        ("null-in-key", {"bad\x00key": "value"}, (), "JSON strings cannot contain null characters."),
        ("invalid-unicode", {"custom": "\ud800"}, (), "Expected a valid UTF-8 JSON object."),
    ):
        cases.append(Case(f"CONFIG-{suffix}", "Collection configuration", suffix, "measurements", "PATCH",
                          changes={"data_collection_config": value},
                          path=("data_collection_config", *path) if path else ("data_collection_config", 0),
                          message=message))
    for resource, fields in RELATIONSHIPS.items():
        for name in ("department", *fields):
            for suffix, value, message in (
                ("text", "abc", "A valid integer is required."),
                ("fraction", "1.5", "A valid integer is required."),
                ("zero", "0", "greater than or equal to 1"),
                ("overflow", str(2**63), "less than or equal to 9223372036854775807"),
            ):
                cases.append(Case(f"FILTER-{resource}-{name}-{suffix}", "Search and filtering",
                                  f"{resource}: {name} filter {suffix}", resource, "GET",
                                  query={name: value}, path=(name, 0), message=message))
    for resource in OPERATIONS[:2]:
        for suffix, value in (("arity", "1,2,3"), ("text", "a,b,c,d"),
                              ("longitude", "-181,0,1,1"), ("latitude", "0,-91,1,1"),
                              ("reversed", "2,0,1,1"), ("zero-height", "0,1,2,1"),
                              ("nan", "nan,0,1,1"), ("infinity", "0,0,inf,1")):
            cases.append(Case(f"FILTER-{resource}-bbox-{suffix}", "Search and filtering",
                              f"{resource}: bbox {suffix}", resource, "GET", query={"bbox": value},
                              path=("bbox",), message="Expected west,south,east,north in WGS84 with increasing coordinates."))
    for suffix, value, message in (("blank", "", "This field may not be blank."),
                                   ("long", "x" * 256, "no more than 255 characters")):
        cases.append(Case(f"FILTER-identifier-{suffix}", "Search and filtering", f"identifier: {suffix}",
                          "network-elements", "GET", query={"identifier": value},
                          path=("identifier", 0), message=message))
    for resource, key in CATALOGS.items():
        cases.append(Case(f"CATALOG-{resource}-duplicate", "Controlled lists", f"{resource}: case-insensitive duplicate",
                          resource, changes={"name": f"$duplicate_{key}"}, actor="catalog-manager",
                          path=("name", 0), message="An active entry already has this name."))
        cases.append(Case(f"CATALOG-{resource}-history-flag", "Controlled lists", f"{resource}: invalid history flag",
                          resource, "GET", query={"include_inactive": "maybe"},
                          path=("include_inactive", 0), message="Must be a valid boolean."))
    for resource in (*OPERATIONS[:2], *CATALOGS):
        cases.append(Case(f"DELETE-{resource}-dependency", "Logical deletion", f"{resource}: active dependency",
                          resource, "DELETE", 409, ("detail",),
                          "Archive the active records that reference this record first.",
                          actor="catalog-manager" if resource in CATALOGS else "editor"))
    for resource in OPERATIONS:
        cases.append(Case(f"AUTH-{resource}-anonymous", "Authentication and permissions", f"{resource}: anonymous request",
                          resource, "GET", 403, ("detail",), "Authentication credentials were not provided.", actor="anonymous"))
        cases.append(Case(f"AUTH-{resource}-unavailable-department", "Authentication and permissions",
                          f"{resource}: policy grants a missing department", resource, "POST", 403,
                          ("detail",), "This department is unavailable.", changes={"department": 999}, setup="missing-department"))
    cases.append(Case("AUTH-shared-lists-no-platform", "Authentication and permissions", "Unconfigured Platform denies catalog writes",
                      "measurement-types", status=403, path=("detail",),
                      message="You do not have write access to the shared lists.", setup="no-platform", actor="catalog-manager"))
    for resource, method, detail in (("physical-devices", "PUT", False), ("physical-devices", "POST", True),
                                     ("imports/excel", "GET", False)):
        cases.append(Case(f"METHOD-{resource.replace('/', '-')}-{method}", "HTTP methods",
                          f"{method} is not supported at {'detail' if detail else 'collection'}", resource,
                          method, 405, ("detail",), f'Method "{method}" not allowed.', setup="detail" if detail else "collection"))
    for value in ("not-a-page", "0", "999999"):
        cases.append(Case(f"PAGE-{value}", "Pagination", f"Invalid page {value}", method="GET", status=404,
                          query={"page": value}, path=("detail",), message="Invalid page."))
    cases.extend((
        Case("CONFIG-nonfinite-number", "Collection configuration", "JSON exponent overflows to infinity",
             "measurements", "PATCH", path=("data_collection_config", 0),
             message="Expected a valid UTF-8 JSON object.", setup="nonfinite-config",
             changes={"data_collection_config": {"custom": "raw JSON number 1e999"}}),
        Case("HTTP-malformed-json", "Request parsing", "Malformed JSON body", "physical-devices", "POST",
             path=("detail",), message="JSON parse error", setup="malformed-json"),
    ))
    return cases


API_CASES = api_cases()

IMPORT_CASES = [
    Case("XLSX-" + key, group, title, "imports/excel", path=path, message=message, setup=key)
    for key, group, title, path, message in (
        ("missing-file", "Import request", "Missing file", ("file", 0), "No file was submitted."),
        ("empty-file", "Import request", "Empty upload", ("file", 0), "The submitted file is empty."),
        ("missing-department", "Import request", "Missing department", ("department", 0), "This field is required."),
        ("invalid-department", "Import request", "Invalid department", ("department", 0), "A valid integer is required."),
        ("suffix", "Workbook file", "Wrong extension", ("file", 0), "Upload an .xlsx workbook of up to 5 MiB."),
        ("upload-limit", "Workbook file", "More than 5 MiB uploaded", ("file", 0), "Upload an .xlsx workbook of up to 5 MiB."),
        ("zip-count", "Workbook file", "More than 200 ZIP members", ("file", 0), "The workbook expands beyond the import limit."),
        ("expanded-limit", "Workbook file", "More than 25 MiB expanded", ("file", 0), "The workbook expands beyond the import limit."),
        ("macro", "Workbook file", "VBA member in uploaded workbook", ("file", 0), "Upload an .xlsx workbook without macros."),
        ("corrupt-zip", "Workbook file", "Unreadable ZIP", ("file", 0), "The file could not be read as an .xlsx workbook."),
        ("malformed-xml", "Workbook file", "Malformed worksheet XML", ("file", 0), "The file could not be read as an .xlsx workbook."),
        ("corrupt-deflate", "Workbook file", "Corrupt compressed member", ("file", 0), "The file could not be read as an .xlsx workbook."),
        ("unknown-sheet", "Workbook structure", "Unknown worksheet", ("sheet", 0), "Unknown worksheet."),
        ("empty", "Workbook structure", "No metadata rows", ("file", 0), "The workbook has no metadata rows."),
        ("header-missing", "Workbook structure", "Missing required header", ("header", 0), "Use unique columns"),
        ("header-duplicate", "Workbook structure", "Duplicate header", ("header", 0), "Use unique columns"),
        ("header-unknown", "Workbook structure", "Unknown header", ("header", 0), "Use unique columns"),
        ("header-blank", "Workbook structure", "Blank interior header", ("header", 0), "Use unique columns"),
        ("extra-cell", "Workbook rows", "Data without a column heading", ("row", 0), "Every value needs a column heading."),
        ("formula", "Workbook rows", "Formula cell", ("name", 0), "Use literal values without formulas or Excel errors."),
        ("excel-error", "Workbook rows", "Excel error cell", ("name", 0), "Use literal values without formulas or Excel errors."),
        ("ref-format", "Workbook rows", "Invalid reference grammar", ("ref", 0), "Use 1 to 64 letters"),
        ("ref-long", "Workbook rows", "Reference longer than 64", ("ref", 0), "Use 1 to 64 letters"),
        ("ref-number", "Workbook rows", "Numeric reference", ("ref", 0), "Use 1 to 64 letters"),
        ("ref-duplicate", "Workbook rows", "Duplicate reference in one sheet", ("ref", 0), "This reference already appears on the sheet."),
        ("row-limit", "Workbook rows", "Data at Excel row 2002", ("row", 0), "Use at most 2000 rows per sheet."),
        ("unresolved-device", "Workbook relationships", "Unresolved Device @ref", ("physical_device", 0), "This workbook reference could not be resolved."),
        ("unresolved-element", "Workbook relationships", "Unresolved Network Element @ref", ("network_element", 0), "This workbook reference could not be resolved."),
        ("identifier-missing-value", "Workbook validation", "Incomplete identifier after an earlier valid row",
         ("external_identifiers", 0, "value", 0), "This field is required."),
    )
]
for column, sheet in (("location", "Physical Devices"), ("geometry", "Network Elements"),
                      ("external_identifiers", "Network Elements"), ("data_collection_config", "Measurements")):
    IMPORT_CASES.append(Case(f"XLSX-json-{column}", "Workbook rows", f"Invalid JSON text in {column}",
                             "imports/excel", path=(column, 0), message="Enter valid JSON as text.",
                             setup=f"json:{sheet}:{column}"))

CLI_CASES = (
    ("CLI-suffix", "Wrong destination suffix", "Use an .xlsx destination."),
    ("CLI-existing", "Existing destination without --force", "Destination already exists. Use --force to replace it."),
    ("CLI-parent", "Missing destination directory", "The destination directory must exist."),
    ("CLI-write", "Filesystem refuses workbook write", "Could not write the workbook:"),
)

DB_CASES = tuple(
    (f"DB-measurement-{name}-required", "Measurement NOT NULL " + name, "required", name, "23502")
    for name in RELATIONSHIPS["measurements"]
) + tuple(
    (f"DB-measurement-{name}-fk", "Measurement foreign key " + name, "foreign-key", name, "23503")
    for name in RELATIONSHIPS["measurements"]
) + tuple(
    (f"DB-{resource}-active-name", "Case-insensitive active catalog uniqueness: " + resource,
     "catalog", key, "23505") for resource, key in CATALOGS.items()
) + (
    ("DB-device-location-type", "PostGIS Point typmod rejects a LineString", "geometry", "type", "22023"),
    ("DB-device-location-srid", "PostGIS SRID typmod rejects 3857", "geometry", "srid", "22023"),
)
