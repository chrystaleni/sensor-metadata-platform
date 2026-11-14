"""Individual API/import/database/CLI error regressions on real PostGIS.

Run a single documented case with pytest -k 'EXT-PATCH-missing-value', for
example. Every rejected request also compares all persisted metadata rows.
"""

from copy import deepcopy
from io import BytesIO, StringIO
import json
import struct
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DataError, IntegrityError, connection, transaction
from openpyxl import load_workbook
from rest_framework.test import APIClient

from local_departments.models import Department
from metadata.imports import MAX_EXPANDED_BYTES, MAX_UPLOAD_BYTES, read_workbook
from metadata.models import (
    ExternalIdentifier, Measurement, MeasurementType, MeasurementUnit,
    NetworkElement, NetworkElementType, PhysicalDevice, PhysicalDeviceType,
)
from metadata.tests.error_cases import API_CASES, CATALOGS, CLI_CASES, DB_CASES, IMPORT_CASES
from metadata.tests.test_backend import API, POLICY, FixturePolicy, create_catalog, make_workbook


pytestmark = pytest.mark.postgis
MODELS = (Department, PhysicalDeviceType, NetworkElementType, MeasurementType,
          MeasurementUnit, PhysicalDevice, NetworkElement, Measurement, ExternalIdentifier)
RELATED = {"device_type": PhysicalDeviceType, "element_type": NetworkElementType,
           "measurement_type": MeasurementType, "measurement_unit": MeasurementUnit,
           "physical_device": PhysicalDevice, "network_element": NetworkElement}


class MissingDepartmentPolicy(FixturePolicy):
    def writable_department_ids(self, request):
        return (*super().writable_department_ids(request), 999)


def database_snapshot():
    # Includes inactive identifiers, actors, timestamps, JSON and geometries,
    # rather than just checking counts or only the affected parent's name.
    return {model._meta.label: json.dumps(list(model.objects.order_by("pk").values()),
                                        default=str, sort_keys=True) for model in MODELS}


@pytest.fixture
def scenario(db, settings):
    settings.METADATA_ACCESS_POLICY = POLICY
    settings.METADATA_PLATFORM_DEPARTMENT_ID = 1
    catalog = create_catalog()
    users = {name: get_user_model().objects.create_user(username=name)
             for name in ("editor", "viewer", "multi", "catalog-manager")}
    device = PhysicalDevice.objects.create(department_id=2, name="Saved device", device_type_id=catalog["device_type"])
    element = NetworkElement.objects.create(department_id=2, name="Saved element", element_type_id=catalog["element_type"])
    measurement = Measurement.objects.create(
        department_id=2, name="Saved measurement", physical_device=device, network_element=element,
        measurement_type_id=catalog["measurement_type"], measurement_unit_id=catalog["measurement_unit"],
        data_collection_config={"existing": True},
    )
    ExternalIdentifier.objects.create(network_element=element, source="ERP", value="existing")
    other_device = PhysicalDevice.objects.create(department_id=3, name="Other device", device_type_id=catalog["device_type"])
    other_element = NetworkElement.objects.create(department_id=3, name="Other element", element_type_id=catalog["element_type"])
    ExternalIdentifier.objects.create(network_element=other_element, source="OTHER", value="claimed")
    tokens = {**catalog, "physical_device": device.pk, "network_element": element.pk,
              "other_physical_device": other_device.pk, "other_network_element": other_element.pk}
    for name in CATALOGS.values():
        model = RELATED[name]
        tokens[f"duplicate_{name}"] = model.objects.get(pk=catalog[name]).name.upper()
    return {"client": APIClient(), "users": users, "tokens": tokens, "catalog": catalog,
            "records": {"physical-devices": device, "network-elements": element, "measurements": measurement}}


def resolve(value, tokens):
    if isinstance(value, str) and value.startswith("$") and value != "$omit":
        return tokens[value[1:]]
    if isinstance(value, list):
        return [resolve(item, tokens) for item in value]
    if isinstance(value, dict):
        return {key: resolve(item, tokens) for key, item in value.items()}
    return value


def base_payload(resource, scenario):
    result = {"name": "New record", "department": 2}
    fields = {"physical-devices": ("device_type",), "network-elements": ("element_type",),
              "measurements": ("physical_device", "network_element", "measurement_type", "measurement_unit")}
    result.update({key: scenario["tokens"][key] for key in fields.get(resource, ())})
    return result


def assert_error(response, case, before, record_property, *, envelope=False):
    assert response.status_code == case.status, response.content
    body = response.json()
    error = body
    if envelope:
        assert set(body) == {"errors"}
        assert len(body["errors"]) == 1, body
        error = body["errors"][0]["errors"]
    for part in case.path:
        # DRF 3.18 encodes nested item errors as objects keyed by index;
        # older DRF releases encode the same errors as lists.
        error = error[str(part) if isinstance(error, dict) and isinstance(part, int) else part]
    assert case.message in str(error), body
    assert database_snapshot() == before, "Rejected operation changed persisted metadata"
    record_property("case_id", case.id)
    record_property("observed_status", response.status_code)
    record_property("observed_error", json.dumps(body, ensure_ascii=True))
    record_property("metadata_unchanged", True)


@pytest.mark.parametrize("case", API_CASES, ids=lambda case: case.id)
def test_api_error_contract(scenario, settings, case, record_property):
    client = scenario["client"]
    if case.actor != "anonymous":
        client.force_authenticate(scenario["users"][case.actor])
    if case.setup.startswith("archive:"):
        name = case.setup.split(":", 1)[1]
        RELATED[name].objects.filter(pk=scenario["tokens"][name]).archive(scenario["users"]["editor"])
    elif case.setup == "missing-department":
        settings.METADATA_ACCESS_POLICY = "metadata.tests.test_error_contract.MissingDepartmentPolicy"
    elif case.setup == "no-platform":
        settings.METADATA_PLATFORM_DEPARTMENT_ID = None
    for value in case.changes.values():
        for name in CATALOGS.values():
            if value == f"$other_{name}":
                tokens = scenario["tokens"]
                tokens[f"other_{name}"] = RELATED[name].objects.create(
                    department_id=3, name="Non-Platform value",
                ).pk
    detail = case.method in {"PATCH", "DELETE", "PUT"}
    if case.setup in {"collection", "detail"}:
        detail = case.setup == "detail"
    url = f"{API}{case.resource}/"
    if detail:
        pk = (scenario["catalog"][CATALOGS[case.resource]] if case.resource in CATALOGS
              else scenario["records"][case.resource].pk)
        url += f"{pk}/"
    data = base_payload(case.resource, scenario) if case.method == "POST" else {}
    for key, value in resolve(deepcopy(case.changes), scenario["tokens"]).items():
        if value == "$omit":
            data.pop(key, None)
        else:
            data[key] = value
    before = database_snapshot()
    if case.method == "GET":
        response = client.get(url, case.query)
    else:
        # Escaped Unicode is legal JSON at the transport layer. The serializer
        # must reject unpaired surrogates before PostgreSQL's UTF-8 conversion.
        body = json.dumps(data, ensure_ascii=True)
        if case.setup == "nonfinite-config":
            body = '{"data_collection_config":{"custom":1e999}}'
        elif case.setup == "malformed-json":
            body = '{"department":2,'
        response = client.generic(case.method, url, body,
                                  content_type="application/json")
    assert_error(response, case, before, record_property)
    if case.id.endswith("missing-both"):
        item_errors = response.json()["external_identifiers"]
        item = item_errors["0"] if isinstance(item_errors, dict) else item_errors[0]
        assert set(item) == {"source", "value"}


def zip_bytes(entries):
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return output.getvalue()


def workbook_upload(case, scenario):
    key = case.setup
    catalog = scenario["catalog"]
    sheets = {"Physical Devices": [("name", "device_type"), ("Imported", catalog["device_type"])]}
    if key == "empty-file":
        return SimpleUploadedFile("empty.xlsx", b"")
    if key == "suffix":
        return SimpleUploadedFile("metadata.xls", b"not-xlsx")
    if key == "upload-limit":
        return SimpleUploadedFile("large.xlsx", b"x" * (MAX_UPLOAD_BYTES + 1))
    if key in {"zip-count", "expanded-limit", "macro", "corrupt-zip"}:
        entries = {f"item-{i}": b"" for i in range(201)} if key == "zip-count" else {}
        if key == "expanded-limit":
            entries["large"] = b"0" * (MAX_EXPANDED_BYTES + 1)
        elif key == "macro":
            entries["XL/vbaProject.bin"] = b"macro"
        return SimpleUploadedFile("bad.xlsx", b"not a zip" if key == "corrupt-zip" else zip_bytes(entries))
    if key == "unknown-sheet":
        sheets = {"Unexpected": [("name",), ("Value",)]}
    elif key == "empty":
        sheets = {"Physical Devices": [("name", "device_type")]}
    elif key.startswith("header-"):
        headers = {"header-missing": ("name",), "header-duplicate": ("name", "device_type", "name"),
                   "header-unknown": ("name", "device_type", "surprise"),
                   "header-blank": ("name", None, "device_type")}[key]
        sheets = {"Physical Devices": [headers]}
    elif key == "extra-cell":
        sheets["Physical Devices"][1] = ("Imported", catalog["device_type"], "unheaded")
    elif key in {"formula", "excel-error"}:
        sheets["Physical Devices"][1] = ("=1+1" if key == "formula" else "#DIV/0!", catalog["device_type"])
    elif key.startswith("ref-"):
        ref = {"ref-format": "@invalid", "ref-long": "r" * 65, "ref-number": 123, "ref-duplicate": "same"}[key]
        sheets = {"Physical Devices": [("name", "device_type", "ref"), ("Imported", catalog["device_type"], ref)]}
        if key == "ref-duplicate":
            sheets["Physical Devices"].append(("Second", catalog["device_type"], ref))
    elif key == "row-limit":
        # A malicious dimension is not trusted; the real row position is capped.
        sheets["Physical Devices"].extend([()] * 1999)
        sheets["Physical Devices"].append(("Too late", catalog["device_type"]))
    elif key.startswith("unresolved-"):
        sheets["Measurements"] = [
            ("name", "physical_device", "network_element", "measurement_type", "measurement_unit"),
            ("Invalid link", "@missing" if key == "unresolved-device" else scenario["tokens"]["physical_device"],
             "@missing" if key == "unresolved-element" else scenario["tokens"]["network_element"],
             catalog["measurement_type"], catalog["measurement_unit"]),
        ]
    elif key == "identifier-missing-value":
        sheets["Network Elements"] = [("name", "element_type", "external_identifiers"),
                                       ("Invalid identifier", catalog["element_type"], '[{"source":"ERP"}]')]
    elif key.startswith("json:"):
        _, sheet, column = key.split(":")
        headers = {"Physical Devices": ("name", "device_type"),
                   "Network Elements": ("name", "element_type"),
                   "Measurements": ("name", "physical_device", "network_element", "measurement_type", "measurement_unit")}[sheet]
        values = ["Bad JSON", *[scenario["tokens"][name] for name in headers[1:]], "{invalid"]
        sheets = {sheet: [(*headers, column), values]}
    upload = make_workbook(sheets)
    if key in {"malformed-xml", "corrupt-deflate"}:
        with ZipFile(upload) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        member = "xl/worksheets/sheet1.xml"
        if key == "malformed-xml":
            entries[member] = b"<unclosed"
        data = bytearray(zip_bytes(entries))
        if key == "corrupt-deflate":
            with ZipFile(BytesIO(data)) as archive:
                offset = archive.getinfo(member).header_offset
            name_length, extra_length = struct.unpack_from("<HH", data, offset + 26)
            # Reserved DEFLATE block type 3 causes zlib.error, not BadZipFile.
            data[offset + 30 + name_length + extra_length] = 0x07
        return SimpleUploadedFile("bad.xlsx", bytes(data))
    return upload


@pytest.mark.parametrize("case", IMPORT_CASES, ids=lambda case: case.id)
def test_import_error_contract(scenario, case, record_property):
    client = scenario["client"]
    client.force_authenticate(scenario["users"]["editor"])
    data = {"department": 2}
    if case.setup != "missing-file":
        data["file"] = workbook_upload(case, scenario)
    if case.setup == "missing-department":
        data.pop("department")
    elif case.setup == "invalid-department":
        data["department"] = "north"
    before = database_snapshot()
    response = client.post(f"{API}imports/excel/", data, format="multipart")
    envelope = case.group != "Import request"
    assert_error(response, case, before, record_property, envelope=envelope)
    if envelope:
        error = response.json()["errors"][0]
        expected_row = (2002 if case.setup == "row-limit" else 1 if case.setup.startswith("header-")
                        else 3 if case.setup == "ref-duplicate" else None
                        if case.group in {"Workbook file", "Workbook structure"} else 2)
        assert error["row"] == expected_row
        if case.group == "Workbook file" or case.setup == "empty":
            assert error["sheet"] is None
        elif case.setup == "unknown-sheet":
            assert error["sheet"] == "Unexpected"
        else:
            assert error["sheet"] in {"Physical Devices", "Network Elements", "Measurements"}


@pytest.mark.parametrize("case_id,title,kind,name,sqlstate", DB_CASES, ids=[case[0] for case in DB_CASES])
def test_database_error_contract(scenario, case_id, title, kind, name, sqlstate, record_property):
    before = database_snapshot()
    with pytest.raises((IntegrityError, DataError)) as caught:
        with transaction.atomic():
            if kind == "required":
                Measurement.objects.filter(pk=scenario["records"]["measurements"].pk).update(**{name + "_id": None})
            elif kind == "foreign-key":
                Measurement.objects.filter(pk=scenario["records"]["measurements"].pk).update(**{name + "_id": 99999999})
                # Django foreign keys are deferred. Force the actual database
                # check inside the savepoint so rejection cannot taint teardown.
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            elif kind == "catalog":
                RELATED[name].objects.create(department_id=1, name=scenario["tokens"][f"duplicate_{name}"])
            else:
                ewkt = "SRID=4326;LINESTRING(0 0,1 1)" if name == "type" else "SRID=3857;POINT(0 0)"
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE metadata_physicaldevice SET location=ST_GeomFromEWKT(%s) WHERE id=%s",
                                   [ewkt, scenario["records"]["physical-devices"].pk])
    assert caught.value.__cause__.sqlstate == sqlstate
    assert database_snapshot() == before
    record_property("case_id", case_id)
    record_property("observed_sqlstate", sqlstate)
    record_property("metadata_unchanged", True)


@pytest.mark.parametrize("case_id,title,message", CLI_CASES, ids=[case[0] for case in CLI_CASES])
def test_workbook_command_error_contract(tmp_path, case_id, title, message, record_property):
    destination = tmp_path / "metadata.xlsx"
    force = False
    if case_id == "CLI-suffix":
        destination = tmp_path / "metadata.csv"
    elif case_id == "CLI-existing":
        destination.write_bytes(b"Preserve this existing file")
    elif case_id == "CLI-parent":
        destination = tmp_path / "missing" / "metadata.xlsx"
    else:
        destination.mkdir()
        (destination / "marker").write_bytes(b"Preserve this directory")
        force = True
    before = {str(path.relative_to(tmp_path)): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    with pytest.raises(CommandError, match=message.replace(".", r"\.")):
        call_command("metadata_workbook", str(destination), force=force, stdout=StringIO())
    after = {str(path.relative_to(tmp_path)): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before
    record_property("case_id", case_id)
    record_property("files_unchanged", True)


def test_session_csrf_error_preserves_metadata(scenario):
    user = scenario["users"]["editor"]
    user.set_password("local-test-password")
    user.save()
    client = APIClient(enforce_csrf_checks=True)
    assert client.login(username="editor", password="local-test-password")
    data = base_payload("physical-devices", scenario)
    before = database_snapshot()
    rejected = client.post(f"{API}physical-devices/", data, format="json")
    assert rejected.status_code == 403
    assert "CSRF" in rejected.json()["detail"]
    assert database_snapshot() == before
    token = "A" * 32
    client.cookies["csrftoken"] = token
    accepted = client.post(f"{API}physical-devices/", data, format="json", HTTP_X_CSRFTOKEN=token)
    assert accepted.status_code == 201, accepted.content
    assert accepted.json()["created_by"] == user.pk


def test_import_requires_multipart_and_preserves_metadata(scenario):
    client = scenario["client"]
    client.force_authenticate(scenario["users"]["editor"])
    before = database_snapshot()
    response = client.post(f"{API}imports/excel/", {"department": 2}, format="json")
    assert response.status_code == 415
    assert "Unsupported media type" in response.json()["detail"]
    assert database_snapshot() == before


@pytest.mark.parametrize("page_size", ["invalid", "0", "-1", "1000"], ids=["invalid", "zero", "negative", "capped"])
def test_pagination_fallback_is_not_an_error(scenario, page_size):
    PhysicalDevice.objects.bulk_create([
        PhysicalDevice(department_id=2, name=f"Device {i}", device_type_id=scenario["catalog"]["device_type"])
        for i in range(110)
    ])
    client = scenario["client"]
    client.force_authenticate(scenario["users"]["editor"])
    before = database_snapshot()
    response = client.get(f"{API}physical-devices/", {"page_size": page_size, "ordering": "unknown"})
    assert response.status_code == 200
    assert len(response.json()["results"]) == (100 if page_size == "1000" else 25)
    ids = [record["id"] for record in response.json()["results"]]
    assert ids == sorted(ids)
    assert database_snapshot() == before


def test_config_and_geometry_valid_boundaries(scenario):
    client = scenario["client"]
    client.force_authenticate(scenario["users"]["editor"])
    for point in ([180, 90], [-180, -90]):
        response = client.patch(f'{API}physical-devices/{scenario["records"]["physical-devices"].pk}/',
                                {"location": {"type": "Point", "coordinates": point}}, format="json")
        assert response.status_code == 200
        assert response.json()["location"]["coordinates"] == point
    path = f'{API}measurements/{scenario["records"]["measurements"].pk}/'
    config = {"protocol": "p" * 50, "endpoint": "e" * 2048, "source_identifier": "s" * 255,
              "extra_settings": {"nested": [True, None, "α"]}, "custom": {"preserved": True}}
    response = client.patch(path, {"data_collection_config": config}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["data_collection_config"] == config
    response = client.patch(path, {"data_collection_config": None}, format="json")
    assert response.status_code == 200
    assert response.json()["data_collection_config"] is None


def test_external_identifiers_accept_exact_limits_and_preserve_retained_id(scenario):
    client = scenario["client"]
    client.force_authenticate(scenario["users"]["editor"])
    element = scenario["records"]["network-elements"]
    existing_id = element.external_identifiers.active().get().pk
    identifiers = [{"source": "ERP", "value": "existing"},
                   {"source": "s" * 120, "value": "v" * 255},
                   *[{"source": "LIMIT", "value": str(i)} for i in range(98)]]
    response = client.patch(f"{API}network-elements/{element.pk}/", {"external_identifiers": identifiers}, format="json")
    assert response.status_code == 200, response.content
    assert len(response.json()["external_identifiers"]) == 100
    assert response.json()["external_identifiers"][0]["id"] == existing_id
    assert element.external_identifiers.active().count() == 100
    assert [{key: item[key] for key in ("source", "value")} for item in response.json()["external_identifiers"]] == identifiers


def test_read_only_audit_fields_ignore_client_values(scenario):
    client = scenario["client"]
    editor = scenario["users"]["editor"]
    client.force_authenticate(editor)
    data = {**base_payload("physical-devices", scenario), "id": 99999999, "created_by": scenario["users"]["viewer"].pk,
            "updated_by": None, "created_at": "2000-01-01T00:00:00Z", "updated_at": "2000-01-01T00:00:00Z",
            "is_active": False}
    response = client.post(f"{API}physical-devices/", data, format="json")
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["id"] != 99999999
    assert body["created_by"] == body["updated_by"] == editor.pk
    assert body["is_active"] is True
    assert not body["created_at"].startswith("2000-")
    assert not body["updated_at"].startswith("2000-")


def test_workbook_row_boundary_and_command_force(tmp_path):
    destination = tmp_path / "template.xlsx"
    call_command("metadata_workbook", str(destination), stdout=StringIO())
    workbook = load_workbook(destination, read_only=True)
    try:
        assert workbook.sheetnames == ["Physical Devices", "Network Elements", "Measurements"]
    finally:
        workbook.close()
    destination.write_bytes(b"old data")
    call_command("metadata_workbook", str(destination), force=True, example=True, stdout=StringIO())
    workbook = load_workbook(destination, read_only=True)
    try:
        assert workbook["Measurements"].max_row == 2
    finally:
        workbook.close()
    # Check exactly 2000 rows at the parser boundary without 2000 unnecessary
    # writes. Actual API imports/relationships are covered by the existing suite.
    rows = [("name", "device_type"), *[(f"Device {i}", 1) for i in range(2000)]]
    records = read_workbook(make_workbook({"Physical Devices": rows}))
    assert len(records["Physical Devices"]) == 2000
