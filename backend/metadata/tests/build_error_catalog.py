"""Build human/machine error documentation from executed tests, without Django.

From backend/:
  python -m pytest -v -o junit_family=xunit1 --junitxml=/tmp/backend-results.xml
  python metadata/tests/build_error_catalog.py --junit /tmp/backend-results.xml

Refuses incomplete/failing results instead of documenting an untested contract.
"""

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import runpy
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
TEST_FILE = "metadata/tests/test_error_contract.py"


def brief(value):
    if isinstance(value, str) and len(value) > 85 and len(set(value)) == 1:
        return f"{value[0]!r} repeated {len(value)} times"
    if isinstance(value, list) and len(value) > 10:
        return f"list of {len(value)} items (exact payload in JSON catalog)"
    if isinstance(value, dict):
        return {key: brief(item) for key, item in value.items()}
    if isinstance(value, list):
        return [brief(item) for item in value]
    return value


def cell(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=True)
    return text.replace("|", "\\|").replace("\n", " ")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", required=True, type=Path)
    args = parser.parse_args()
    results = ET.parse(args.junit)
    tests = list(results.iter("testcase"))
    if not tests or any(test.find(tag) is not None for test in tests for tag in ("failure", "error", "skipped")):
        raise SystemExit("Require a complete passing backend JUnit report; documentation was not changed.")
    cases = runpy.run_path(str(Path(__file__).with_name("error_cases.py")))
    observed = {test.attrib["name"]: test for test in tests}
    entries = []
    for collection, function in (("API_CASES", "test_api_error_contract"), ("IMPORT_CASES", "test_import_error_contract")):
        for case in cases[collection]:
            node = f"{function}[{case.id}]"
            test = observed.get(node)
            if test is None:
                raise SystemExit(f"Missing executed case {node}; documentation was not changed.")
            properties = {item.attrib["name"]: item.attrib["value"] for item in test.findall("properties/property")}
            if properties.get("case_id") != case.id or properties.get("metadata_unchanged") != "True":
                raise SystemExit(f"Missing integrity evidence for {node}; use junit_family=xunit1.")
            entries.append({**asdict(case), "kind": collection, "pytest_node": f"{TEST_FILE}::{node}",
                            "observed_status": int(properties["observed_status"]),
                            "observed_response": json.loads(properties["observed_error"]),
                            "metadata_unchanged": True, "result": "passed"})
    for collection, function in (("DB_CASES", "test_database_error_contract"), ("CLI_CASES", "test_workbook_command_error_contract")):
        for case in cases[collection]:
            case_id, title, *_ = case
            node = f"{function}[{case_id}]"
            test = observed.get(node)
            if test is None:
                raise SystemExit(f"Missing executed case {node}; documentation was not changed.")
            properties = {item.attrib["name"]: item.attrib["value"] for item in test.findall("properties/property")}
            if properties.get("case_id") != case_id or properties.get(
                "metadata_unchanged" if collection == "DB_CASES" else "files_unchanged"
            ) != "True":
                raise SystemExit(f"Missing integrity evidence for {node}; use junit_family=xunit1.")
            entries.append({"id": case_id, "title": title, "kind": collection,
                            "pytest_node": f"{TEST_FILE}::{node}", "expectation": case[4] if collection == "DB_CASES" else case[2],
                            "observations": properties, "result": "passed"})
    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise SystemExit("Duplicate case IDs; documentation was not changed.")
    counts = Counter(entry["kind"] for entry in entries)
    lines = [
        "# Backend error contract and individual regression tests", "",
        f"Argyris Fellas. Generated {date.today().isoformat()} from executable cases and a passing local JUnit report.", "",
        f"This catalog records **{len(entries)} individual error cases**: {counts['API_CASES']} REST cases, "
        f"{counts['IMPORT_CASES']} Excel cases, {counts['DB_CASES']} database cases and {counts['CLI_CASES']} command errors. "
        "Additional positive/boundary and session tests are listed below. The pre-existing CRUD, permission and concurrency tests remain enabled.", "",
        "## How to reproduce one case", "", "Run from `backend/`, against an isolated PostGIS test database:", "",
        "```sh", "python -m pytest -v 'metadata/tests/test_error_contract.py::test_api_error_contract[EXT-PATCH-missing-value]'",
        "python -m pytest -v -o junit_family=xunit1 --junitxml=/tmp/backend-results.xml",
        "python metadata/tests/build_error_catalog.py --junit /tmp/backend-results.xml", "```", "",
        "The generator refuses failing, skipped or missing case results. It does not change the database or require a CI workflow modification. "
        "The [JSON catalog](backend-error-cases.json) contains exact payload changes, complete observed HTTP error bodies and full pytest node IDs. "
        "Long repeated strings and lists are abbreviated only in this Markdown table.", "",
        "## Fixtures, error shapes and integrity assertions", "",
        "POST cases start from a valid request; PATCH cases start from existing records. `changes` replaces the shown fields. "
        "`$omit` removes a field. Other `$tokens` resolve to real database IDs: types/units belong to Platform, operational parents to Department 2, "
        "and `$other_*` references belong to Department 3. `archive:field` archives that reference before taking the snapshot. "
        "The actor is an authenticated editor unless the row says otherwise; catalogs use catalog-manager for writes. "
        "The fixture has a linked Measurement, Device, Network Element, an existing ERP identifier and another Network Element's claimed identifier in the same Department.", "",
        "Every negative API/import case compares all nine Department/metadata tables before and after the request, including inactive identifiers, "
        "audit actors, timestamps, JSON and geometry. Database cases use real SQL/ORM failures inside savepoints and make the same comparison. "
        "CLI errors preserve existing file contents. PostgreSQL sequences may advance on rolled-back inserts; sequence values are not business records.", "",
        "Field errors are field-keyed JSON. Nested identifier errors identify the item index (DRF 3.18 uses object keys such as `\"0\"`; "
        "older DRF releases use lists). Workbook parsing/row errors use `errors: [{sheet, row, errors}]`; invalid/missing multipart request fields "
        "use ordinary field-keyed JSON. Authentication/permission/method/conflict errors have `detail`. Human messages are serialized; "
        "DRF's internal ErrorDetail codes are not additional response JSON fields.", "",
        "Identifier uniqueness is Department-scoped after migration 0005. The duplicate fixture uses another element in the same Department; claims in other Departments must not trigger a duplicate error. The [Department identifier handover](../development/pr27-identifier-departments.md) records the 24 dedicated isolation/concurrency/migration regressions and their exact test IDs.", "",
        "## REST errors", "", "All paths have the `/api/v1/` prefix. PATCH/DELETE use an existing record's detail URL; "
        "the METHOD cases explicitly distinguish detail and collection. Error paths below are relative to the error body.", "",
    ]
    previous_group = None
    for entry in entries:
        if entry["kind"] != "API_CASES":
            continue
        if entry["group"] != previous_group:
            previous_group = entry["group"]
            lines += [f"### {previous_group}", "", "| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |",
                      "| --- | --- | --- |"]
        request = f"{entry['method']} {entry['resource']}; " + cell(brief(entry["query"] or entry["changes"]))
        if entry["setup"]:
            request += "; setup=" + entry["setup"]
        if entry["actor"] != "editor":
            request += "; actor=" + entry["actor"]
        path = ".".join(map(str, entry["path"]))
        lines.append(f"| `{entry['id']}` | {request} | {entry['status']}; `{path}`: {cell(entry['message'])} |")
    lines += ["", "## Excel errors", "", "Each ID is a separate parameter of `test_import_error_contract`. "
              "The JSON catalog records the observed sheet and Excel row number. All cases preserve the complete database snapshot. "
              "The unresolved-reference and incomplete-identifier cases deliberately include an earlier valid row to prove whole-workbook rollback.", "",
              "| Case ID | Input / precondition | Expected HTTP and error |", "| --- | --- | --- |"]
    for entry in entries:
        if entry["kind"] == "IMPORT_CASES":
            lines.append(f"| `{entry['id']}` | {entry['title']} (`{entry['setup']}` fixture) | 400; {cell(entry['message'])} |")
    lines += ["", "Excel limits are 5 MiB uploaded, 25 MiB expanded, 200 ZIP members and 2000 worksheet rows below the header. "
              "Blank gaps count towards the last row position; row 2002 is rejected. Header-only sheets do not import records. "
              "These are current implementation limits, not newly introduced features.", "",
              "## Database and command errors", "", "| Case ID | Operation | Expected failure and preservation |", "| --- | --- | --- |"]
    for entry in entries:
        if entry["kind"] in {"DB_CASES", "CLI_CASES"}:
            result = ("SQLSTATE " + entry["expectation"] + "; unchanged metadata" if entry["kind"] == "DB_CASES"
                      else "CommandError: " + entry["expectation"] + "; existing files unchanged")
            lines.append(f"| `{entry['id']}` | {entry['title']} | {cell(result)} |")
    lines += ["", "## Positive, boundary and existing integration coverage", "",
              "| Test | Expected behavior |", "| --- | --- |",
              "| `test_session_csrf_error_preserves_metadata` | Actual Django session: missing CSRF returns 403 with unchanged metadata; matching cookie/header permits creation (201). |",
              "| `test_import_requires_multipart_and_preserves_metadata` | JSON request to the multipart-only endpoint returns 415 with unchanged metadata. |",
              "| `test_pagination_fallback_is_not_an_error` (four parameters) | Invalid/zero/negative page size defaults to 25; 1000 caps at 100. Unknown ordering is ignored; results retain stable ID ordering. |",
              "| `test_config_and_geometry_valid_boundaries` | Accept longitude/latitude endpoints; exact config string limits and arbitrary JSON keys persist; optional config can be null. |",
              "| `test_external_identifiers_accept_exact_limits_and_preserve_retained_id` | Accept exactly 100 identifiers, source length 120 and value length 255; retain the existing identifier's ID. |",
              "| `test_read_only_audit_fields_ignore_client_values` | Submitted ID, actor, timestamp and is_active fields are ignored; the backend assigns the actual actor/time and active status. |",
              "| `test_workbook_row_boundary_and_command_force` | Generate all three sheets; --force replaces the file; exactly 2000 data rows parse successfully. |",
              "| Existing `test_linked_crud_archival_and_dependencies` | Create/read/update/archive all three domains; six dependency conflicts; protected physical deletion and audit actors. |",
              "| Existing identifier PATCH/history tests | Valid/omitted/empty lists, missing source/value/mixed list, stable retained IDs, archived history and atomic rejection. |",
              "| Existing scope/default-deny/catalog tests | Read-only 403 on PATCH/DELETE across three domains; out-of-scope details 404; default deny, scoped search, catalog management and historical references. |",
              "| Existing PostGIS/constraint tests | Cross-Department composite foreign keys, unsupported Network geometry and Department-scoped active external-system identifier uniqueness. |",
              "| Existing Excel workflows | Linked three-domain import, generated example, optional accounts/config, wrong-Department references, late invalid row and duplicate identifier rollback. |",
              "| Existing four concurrency tests | Measurement creation waits for Device/catalog archive; racing identifier API/import writers in one Department receive 400 and preserve integrity. |",
              "| `core/tests/test_health.py`, `core/tests/test_database.py` | GET health status/JSON and actual PostGIS engine/extension query. |", "",
              "Exact existing names and node IDs are in the JUnit report and [acceptance mapping](argyris-backend-validation.md).", "",
              "## Reproduced defect and scope limits", "",
              "`XLSX-corrupt-deflate` first reproduced an uncaught `zlib.error` and HTTP 500. The only production change in the 14 November error audit "
              "adds that concrete decompression exception to the existing unreadable-workbook handler. It now returns the existing file error with HTTP 400. "
              "No endpoint, schema, migration, frontend or CI workflow changed.", "",
              "FixturePolicy supplies synthetic scopes through the existing adapter. This catalog verifies backend enforcement, an actual Django session/CSRF exchange "
              "and default-deny behavior; it does not implement or certify the team's future login endpoint, API keys, production User-Department membership or role adapter. "
              "The Department integration decision remains in the [shared handover](../development/pr27-shared-integration.md). "
              "Unexpected server/database outages and an invalid administrator-supplied adapter path are operational failures, not invented client 400 responses. "
              "The suite exercises the enumerated contracts and boundaries; it is not a claim to test every possible file or third-party library exception.", ""]
    output = ROOT / "docs/testing"
    output.mkdir(parents=True, exist_ok=True)
    (output / "backend-error-catalog.md").write_text("\n".join(lines), encoding="utf-8")
    (output / "backend-error-cases.json").write_text(json.dumps({"generated": date.today().isoformat(),
        "case_count": len(entries), "cases": entries}, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"Documented {len(entries)} individually executed error cases; {len(tests)} passing JUnit records inspected.")


if __name__ == "__main__":
    main()
