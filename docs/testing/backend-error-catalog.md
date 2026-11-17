# Backend error contract and individual regression tests

Argyris Fellas. Generated 2026-11-15 from executable cases and a passing local JUnit report.

This catalog records **310 individual error cases**: 259 REST cases, 33 Excel cases, 14 database cases and 4 command errors. Additional positive/boundary and session tests are listed below. The pre-existing CRUD, permission and concurrency tests remain enabled.

## How to reproduce one case

Run from `backend/`, against an isolated PostGIS test database:

```sh
python -m pytest -v 'metadata/tests/test_error_contract.py::test_api_error_contract[EXT-PATCH-missing-value]'
python -m pytest -v -o junit_family=xunit1 --junitxml=/tmp/backend-results.xml
python metadata/tests/build_error_catalog.py --junit /tmp/backend-results.xml
```

The generator refuses failing, skipped or missing case results. It does not change the database or require a CI workflow modification. The [JSON catalog](backend-error-cases.json) contains exact payload changes, complete observed HTTP error bodies and full pytest node IDs. Long repeated strings and lists are abbreviated only in this Markdown table.

## Fixtures, error shapes and integrity assertions

POST cases start from a valid request; PATCH cases start from existing records. `changes` replaces the shown fields. `$omit` removes a field. Other `$tokens` resolve to real database IDs: types/units belong to Platform, operational parents to Department 2, and `$other_*` references belong to Department 3. `archive:field` archives that reference before taking the snapshot. The actor is an authenticated editor unless the row says otherwise; catalogs use catalog-manager for writes. The fixture has a linked Measurement, Device, Network Element, an existing ERP identifier and another Network Element's claimed identifier in the same Department.

Every negative API/import case compares all nine Department/metadata tables before and after the request, including inactive identifiers, audit actors, timestamps, JSON and geometry. Database cases use real SQL/ORM failures inside savepoints and make the same comparison. CLI errors preserve existing file contents. PostgreSQL sequences may advance on rolled-back inserts; sequence values are not business records.

Field errors are field-keyed JSON. Nested identifier errors identify the item index (DRF 3.18 uses object keys such as `"0"`; older DRF releases use lists). Workbook parsing/row errors use `errors: [{sheet, row, errors}]`; invalid/missing multipart request fields use ordinary field-keyed JSON. Authentication/permission/method/conflict errors have `detail`. Human messages are serialized; DRF's internal ErrorDetail codes are not additional response JSON fields.

Identifier uniqueness is Department-scoped after migration 0005. The duplicate fixture uses another element in the same Department; claims in other Departments must not trigger a duplicate error. The [Department identifier handover](../development/pr27-identifier-departments.md) records the 24 dedicated isolation/concurrency/migration regressions and their exact test IDs.

## REST errors

All paths have the `/api/v1/` prefix. PATCH/DELETE use an existing record's detail URL; the METHOD cases explicitly distinguish detail and collection. Error paths below are relative to the error body.

### Required fields and limits

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `FIELD-physical-devices-name-missing` | POST physical-devices; {"name": "$omit"} | 400; `name.0`: This field is required. |
| `FIELD-physical-devices-name-blank` | POST physical-devices; {"name": " "} | 400; `name.0`: This field may not be blank. |
| `FIELD-physical-devices-name-null` | POST physical-devices; {"name": null} | 400; `name.0`: This field may not be null. |
| `FIELD-physical-devices-name-long` | POST physical-devices; {"name": "'n' repeated 121 times"} | 400; `name.0`: no more than 120 characters |
| `FIELD-physical-devices-description-null` | POST physical-devices; {"description": null} | 400; `description.0`: This field may not be null. |
| `FIELD-network-elements-name-missing` | POST network-elements; {"name": "$omit"} | 400; `name.0`: This field is required. |
| `FIELD-network-elements-name-blank` | POST network-elements; {"name": " "} | 400; `name.0`: This field may not be blank. |
| `FIELD-network-elements-name-null` | POST network-elements; {"name": null} | 400; `name.0`: This field may not be null. |
| `FIELD-network-elements-name-long` | POST network-elements; {"name": "'n' repeated 121 times"} | 400; `name.0`: no more than 120 characters |
| `FIELD-network-elements-description-null` | POST network-elements; {"description": null} | 400; `description.0`: This field may not be null. |
| `FIELD-measurements-name-missing` | POST measurements; {"name": "$omit"} | 400; `name.0`: This field is required. |
| `FIELD-measurements-name-blank` | POST measurements; {"name": " "} | 400; `name.0`: This field may not be blank. |
| `FIELD-measurements-name-null` | POST measurements; {"name": null} | 400; `name.0`: This field may not be null. |
| `FIELD-measurements-name-long` | POST measurements; {"name": "'n' repeated 121 times"} | 400; `name.0`: no more than 120 characters |
| `FIELD-measurements-description-null` | POST measurements; {"description": null} | 400; `description.0`: This field may not be null. |
| `FIELD-physical-device-types-name-missing` | POST physical-device-types; {"name": "$omit"}; actor=catalog-manager | 400; `name.0`: This field is required. |
| `FIELD-physical-device-types-name-blank` | POST physical-device-types; {"name": " "}; actor=catalog-manager | 400; `name.0`: This field may not be blank. |
| `FIELD-physical-device-types-name-null` | POST physical-device-types; {"name": null}; actor=catalog-manager | 400; `name.0`: This field may not be null. |
| `FIELD-physical-device-types-name-long` | POST physical-device-types; {"name": "'n' repeated 121 times"}; actor=catalog-manager | 400; `name.0`: no more than 120 characters |
| `FIELD-physical-device-types-description-null` | POST physical-device-types; {"description": null}; actor=catalog-manager | 400; `description.0`: This field may not be null. |
| `FIELD-network-element-types-name-missing` | POST network-element-types; {"name": "$omit"}; actor=catalog-manager | 400; `name.0`: This field is required. |
| `FIELD-network-element-types-name-blank` | POST network-element-types; {"name": " "}; actor=catalog-manager | 400; `name.0`: This field may not be blank. |
| `FIELD-network-element-types-name-null` | POST network-element-types; {"name": null}; actor=catalog-manager | 400; `name.0`: This field may not be null. |
| `FIELD-network-element-types-name-long` | POST network-element-types; {"name": "'n' repeated 121 times"}; actor=catalog-manager | 400; `name.0`: no more than 120 characters |
| `FIELD-network-element-types-description-null` | POST network-element-types; {"description": null}; actor=catalog-manager | 400; `description.0`: This field may not be null. |
| `FIELD-measurement-types-name-missing` | POST measurement-types; {"name": "$omit"}; actor=catalog-manager | 400; `name.0`: This field is required. |
| `FIELD-measurement-types-name-blank` | POST measurement-types; {"name": " "}; actor=catalog-manager | 400; `name.0`: This field may not be blank. |
| `FIELD-measurement-types-name-null` | POST measurement-types; {"name": null}; actor=catalog-manager | 400; `name.0`: This field may not be null. |
| `FIELD-measurement-types-name-long` | POST measurement-types; {"name": "'n' repeated 121 times"}; actor=catalog-manager | 400; `name.0`: no more than 120 characters |
| `FIELD-measurement-types-description-null` | POST measurement-types; {"description": null}; actor=catalog-manager | 400; `description.0`: This field may not be null. |
| `FIELD-measurement-units-name-missing` | POST measurement-units; {"name": "$omit"}; actor=catalog-manager | 400; `name.0`: This field is required. |
| `FIELD-measurement-units-name-blank` | POST measurement-units; {"name": " "}; actor=catalog-manager | 400; `name.0`: This field may not be blank. |
| `FIELD-measurement-units-name-null` | POST measurement-units; {"name": null}; actor=catalog-manager | 400; `name.0`: This field may not be null. |
| `FIELD-measurement-units-name-long` | POST measurement-units; {"name": "'n' repeated 121 times"}; actor=catalog-manager | 400; `name.0`: no more than 120 characters |
| `FIELD-measurement-units-description-null` | POST measurement-units; {"description": null}; actor=catalog-manager | 400; `description.0`: This field may not be null. |
### Department selection

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `DEPT-physical-devices-missing` | POST physical-devices; {"department": "$omit"} | 400; `department.0`: This field is required. |
| `DEPT-physical-devices-null` | POST physical-devices; {"department": null} | 400; `department.0`: This field may not be null. |
| `DEPT-physical-devices-text` | POST physical-devices; {"department": "north"} | 400; `department.0`: A valid integer is required. |
| `DEPT-physical-devices-zero` | POST physical-devices; {"department": 0} | 400; `department.0`: greater than or equal to 1 |
| `DEPT-physical-devices-overflow` | POST physical-devices; {"department": 9223372036854775808} | 400; `department.0`: less than or equal to 9223372036854775807 |
| `DEPT-physical-devices-immutable` | PATCH physical-devices; {"department": 3}; actor=multi | 400; `department.0`: The department is fixed when the record is created. |
| `DEPT-network-elements-missing` | POST network-elements; {"department": "$omit"} | 400; `department.0`: This field is required. |
| `DEPT-network-elements-null` | POST network-elements; {"department": null} | 400; `department.0`: This field may not be null. |
| `DEPT-network-elements-text` | POST network-elements; {"department": "north"} | 400; `department.0`: A valid integer is required. |
| `DEPT-network-elements-zero` | POST network-elements; {"department": 0} | 400; `department.0`: greater than or equal to 1 |
| `DEPT-network-elements-overflow` | POST network-elements; {"department": 9223372036854775808} | 400; `department.0`: less than or equal to 9223372036854775807 |
| `DEPT-network-elements-immutable` | PATCH network-elements; {"department": 3}; actor=multi | 400; `department.0`: The department is fixed when the record is created. |
| `DEPT-measurements-missing` | POST measurements; {"department": "$omit"} | 400; `department.0`: This field is required. |
| `DEPT-measurements-null` | POST measurements; {"department": null} | 400; `department.0`: This field may not be null. |
| `DEPT-measurements-text` | POST measurements; {"department": "north"} | 400; `department.0`: A valid integer is required. |
| `DEPT-measurements-zero` | POST measurements; {"department": 0} | 400; `department.0`: greater than or equal to 1 |
| `DEPT-measurements-overflow` | POST measurements; {"department": 9223372036854775808} | 400; `department.0`: less than or equal to 9223372036854775807 |
| `DEPT-measurements-immutable` | PATCH measurements; {"department": 3}; actor=multi | 400; `department.0`: The department is fixed when the record is created. |
### Relationships

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `REL-physical-devices-device_type-missing` | POST physical-devices; {"device_type": "$omit"} | 400; `device_type.0`: This field is required. |
| `REL-physical-devices-device_type-null` | POST physical-devices; {"device_type": null} | 400; `device_type.0`: This field may not be null. |
| `REL-physical-devices-device_type-fraction` | POST physical-devices; {"device_type": 1.5} | 400; `device_type.0`: A valid integer is required. |
| `REL-physical-devices-device_type-zero` | POST physical-devices; {"device_type": 0} | 400; `device_type.0`: object does not exist |
| `REL-physical-devices-device_type-overflow` | POST physical-devices; {"device_type": 9223372036854775808} | 400; `device_type.0`: object does not exist |
| `REL-physical-devices-device_type-absent` | POST physical-devices; {"device_type": 99999999} | 400; `device_type.0`: object does not exist |
| `REL-physical-devices-device_type-scope` | POST physical-devices; {"device_type": "$other_device_type"} | 400; `device_type.0`: object does not exist |
| `REL-physical-devices-device_type-archived` | POST physical-devices; {}; setup=archive:device_type | 400; `device_type.0`: object does not exist |
| `REL-physical-devices-device_type-unchanged-archived` | PATCH physical-devices; {"name": "Attempted edit"}; setup=archive:device_type | 400; `device_type.0`: Choose an active record in the permitted department. |
| `REL-network-elements-element_type-missing` | POST network-elements; {"element_type": "$omit"} | 400; `element_type.0`: This field is required. |
| `REL-network-elements-element_type-null` | POST network-elements; {"element_type": null} | 400; `element_type.0`: This field may not be null. |
| `REL-network-elements-element_type-fraction` | POST network-elements; {"element_type": 1.5} | 400; `element_type.0`: A valid integer is required. |
| `REL-network-elements-element_type-zero` | POST network-elements; {"element_type": 0} | 400; `element_type.0`: object does not exist |
| `REL-network-elements-element_type-overflow` | POST network-elements; {"element_type": 9223372036854775808} | 400; `element_type.0`: object does not exist |
| `REL-network-elements-element_type-absent` | POST network-elements; {"element_type": 99999999} | 400; `element_type.0`: object does not exist |
| `REL-network-elements-element_type-scope` | POST network-elements; {"element_type": "$other_element_type"} | 400; `element_type.0`: object does not exist |
| `REL-network-elements-element_type-archived` | POST network-elements; {}; setup=archive:element_type | 400; `element_type.0`: object does not exist |
| `REL-network-elements-element_type-unchanged-archived` | PATCH network-elements; {"name": "Attempted edit"}; setup=archive:element_type | 400; `element_type.0`: Choose an active record in the permitted department. |
| `REL-measurements-physical_device-missing` | POST measurements; {"physical_device": "$omit"} | 400; `physical_device.0`: This field is required. |
| `REL-measurements-physical_device-null` | POST measurements; {"physical_device": null} | 400; `physical_device.0`: This field may not be null. |
| `REL-measurements-physical_device-fraction` | POST measurements; {"physical_device": 1.5} | 400; `physical_device.0`: A valid integer is required. |
| `REL-measurements-physical_device-zero` | POST measurements; {"physical_device": 0} | 400; `physical_device.0`: object does not exist |
| `REL-measurements-physical_device-overflow` | POST measurements; {"physical_device": 9223372036854775808} | 400; `physical_device.0`: object does not exist |
| `REL-measurements-physical_device-absent` | POST measurements; {"physical_device": 99999999} | 400; `physical_device.0`: object does not exist |
| `REL-measurements-physical_device-scope` | POST measurements; {"physical_device": "$other_physical_device"} | 400; `physical_device.0`: object does not exist |
| `REL-measurements-physical_device-archived` | POST measurements; {}; setup=archive:physical_device | 400; `physical_device.0`: object does not exist |
| `REL-measurements-physical_device-unchanged-archived` | PATCH measurements; {"name": "Attempted edit"}; setup=archive:physical_device | 400; `physical_device.0`: Choose an active record in the permitted department. |
| `REL-measurements-network_element-missing` | POST measurements; {"network_element": "$omit"} | 400; `network_element.0`: This field is required. |
| `REL-measurements-network_element-null` | POST measurements; {"network_element": null} | 400; `network_element.0`: This field may not be null. |
| `REL-measurements-network_element-fraction` | POST measurements; {"network_element": 1.5} | 400; `network_element.0`: A valid integer is required. |
| `REL-measurements-network_element-zero` | POST measurements; {"network_element": 0} | 400; `network_element.0`: object does not exist |
| `REL-measurements-network_element-overflow` | POST measurements; {"network_element": 9223372036854775808} | 400; `network_element.0`: object does not exist |
| `REL-measurements-network_element-absent` | POST measurements; {"network_element": 99999999} | 400; `network_element.0`: object does not exist |
| `REL-measurements-network_element-scope` | POST measurements; {"network_element": "$other_network_element"} | 400; `network_element.0`: object does not exist |
| `REL-measurements-network_element-archived` | POST measurements; {}; setup=archive:network_element | 400; `network_element.0`: object does not exist |
| `REL-measurements-network_element-unchanged-archived` | PATCH measurements; {"name": "Attempted edit"}; setup=archive:network_element | 400; `network_element.0`: Choose an active record in the permitted department. |
| `REL-measurements-measurement_type-missing` | POST measurements; {"measurement_type": "$omit"} | 400; `measurement_type.0`: This field is required. |
| `REL-measurements-measurement_type-null` | POST measurements; {"measurement_type": null} | 400; `measurement_type.0`: This field may not be null. |
| `REL-measurements-measurement_type-fraction` | POST measurements; {"measurement_type": 1.5} | 400; `measurement_type.0`: A valid integer is required. |
| `REL-measurements-measurement_type-zero` | POST measurements; {"measurement_type": 0} | 400; `measurement_type.0`: object does not exist |
| `REL-measurements-measurement_type-overflow` | POST measurements; {"measurement_type": 9223372036854775808} | 400; `measurement_type.0`: object does not exist |
| `REL-measurements-measurement_type-absent` | POST measurements; {"measurement_type": 99999999} | 400; `measurement_type.0`: object does not exist |
| `REL-measurements-measurement_type-scope` | POST measurements; {"measurement_type": "$other_measurement_type"} | 400; `measurement_type.0`: object does not exist |
| `REL-measurements-measurement_type-archived` | POST measurements; {}; setup=archive:measurement_type | 400; `measurement_type.0`: object does not exist |
| `REL-measurements-measurement_type-unchanged-archived` | PATCH measurements; {"name": "Attempted edit"}; setup=archive:measurement_type | 400; `measurement_type.0`: Choose an active record in the permitted department. |
| `REL-measurements-measurement_unit-missing` | POST measurements; {"measurement_unit": "$omit"} | 400; `measurement_unit.0`: This field is required. |
| `REL-measurements-measurement_unit-null` | POST measurements; {"measurement_unit": null} | 400; `measurement_unit.0`: This field may not be null. |
| `REL-measurements-measurement_unit-fraction` | POST measurements; {"measurement_unit": 1.5} | 400; `measurement_unit.0`: A valid integer is required. |
| `REL-measurements-measurement_unit-zero` | POST measurements; {"measurement_unit": 0} | 400; `measurement_unit.0`: object does not exist |
| `REL-measurements-measurement_unit-overflow` | POST measurements; {"measurement_unit": 9223372036854775808} | 400; `measurement_unit.0`: object does not exist |
| `REL-measurements-measurement_unit-absent` | POST measurements; {"measurement_unit": 99999999} | 400; `measurement_unit.0`: object does not exist |
| `REL-measurements-measurement_unit-scope` | POST measurements; {"measurement_unit": "$other_measurement_unit"} | 400; `measurement_unit.0`: object does not exist |
| `REL-measurements-measurement_unit-archived` | POST measurements; {}; setup=archive:measurement_unit | 400; `measurement_unit.0`: object does not exist |
| `REL-measurements-measurement_unit-unchanged-archived` | PATCH measurements; {"name": "Attempted edit"}; setup=archive:measurement_unit | 400; `measurement_unit.0`: Choose an active record in the permitted department. |
### Optional field limits

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `FIELD-dma_model_id-null` | POST network-elements; {"dma_model_id": null} | 400; `dma_model_id.0`: This field may not be null. |
| `FIELD-dma_model_id-long` | POST network-elements; {"dma_model_id": "'x' repeated 256 times"} | 400; `dma_model_id.0`: no more than 255 characters |
| `FIELD-strategic_model_id-null` | POST network-elements; {"strategic_model_id": null} | 400; `strategic_model_id.0`: This field may not be null. |
| `FIELD-strategic_model_id-long` | POST network-elements; {"strategic_model_id": "'x' repeated 256 times"} | 400; `strategic_model_id.0`: no more than 255 characters |
| `FIELD-customer_account-null` | POST measurements; {"customer_account": null} | 400; `customer_account.0`: This field may not be null. |
| `FIELD-customer_account-long` | POST measurements; {"customer_account": "'x' repeated 256 times"} | 400; `customer_account.0`: no more than 255 characters |
| `FIELD-meter_account-null` | POST measurements; {"meter_account": null} | 400; `meter_account.0`: This field may not be null. |
| `FIELD-meter_account-long` | POST measurements; {"meter_account": "'x' repeated 256 times"} | 400; `meter_account.0`: no more than 255 characters |
| `FIELD-symbol-null` | POST measurement-units; {"symbol": null}; actor=catalog-manager | 400; `symbol.0`: This field may not be null. |
| `FIELD-symbol-long` | POST measurement-units; {"symbol": "xxxxxxxxxxxxxxxxxxxxxxxxx"}; actor=catalog-manager | 400; `symbol.0`: no more than 24 characters |
### External identifiers

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `EXT-POST-missing-source` | POST network-elements; {"external_identifiers": [{"value": "new"}]} | 400; `external_identifiers.0.source.0`: This field is required. |
| `EXT-PATCH-missing-source` | PATCH network-elements; {"external_identifiers": [{"value": "new"}]} | 400; `external_identifiers.0.source.0`: This field is required. |
| `EXT-POST-missing-value` | POST network-elements; {"external_identifiers": [{"source": "ERP"}]} | 400; `external_identifiers.0.value.0`: This field is required. |
| `EXT-PATCH-missing-value` | PATCH network-elements; {"external_identifiers": [{"source": "ERP"}]} | 400; `external_identifiers.0.value.0`: This field is required. |
| `EXT-POST-missing-both` | POST network-elements; {"external_identifiers": [{}]} | 400; `external_identifiers.0.source.0`: This field is required. |
| `EXT-PATCH-missing-both` | PATCH network-elements; {"external_identifiers": [{}]} | 400; `external_identifiers.0.source.0`: This field is required. |
| `EXT-source-blank` | PATCH network-elements; {"external_identifiers": [{"source": " ", "value": "new"}]} | 400; `external_identifiers.0.source.0`: This field may not be blank. |
| `EXT-source-null` | PATCH network-elements; {"external_identifiers": [{"source": null, "value": "new"}]} | 400; `external_identifiers.0.source.0`: This field may not be null. |
| `EXT-source-long` | PATCH network-elements; {"external_identifiers": [{"source": "'x' repeated 121 times", "value": "new"}]} | 400; `external_identifiers.0.source.0`: no more than 120 characters |
| `EXT-value-blank` | PATCH network-elements; {"external_identifiers": [{"source": "ERP", "value": " "}]} | 400; `external_identifiers.0.value.0`: This field may not be blank. |
| `EXT-value-null` | PATCH network-elements; {"external_identifiers": [{"source": "ERP", "value": null}]} | 400; `external_identifiers.0.value.0`: This field may not be null. |
| `EXT-value-long` | PATCH network-elements; {"external_identifiers": [{"source": "ERP", "value": "'x' repeated 256 times"}]} | 400; `external_identifiers.0.value.0`: no more than 255 characters |
| `EXT-null-list` | PATCH network-elements; {"external_identifiers": null, "name": "Attempted edit"} | 400; `external_identifiers.0`: This field may not be null. |
| `EXT-object-not-list` | PATCH network-elements; {"external_identifiers": {}, "name": "Attempted edit"} | 400; `external_identifiers.non_field_errors.0`: Expected a list |
| `EXT-scalar-item` | PATCH network-elements; {"external_identifiers": ["ERP"], "name": "Attempted edit"} | 400; `external_identifiers.0.non_field_errors.0`: Expected a dictionary |
| `EXT-too-many` | PATCH network-elements; {"external_identifiers": "list of 101 items (exact payload in JSON catalog)", "name": "Attempted edit"} | 400; `external_identifiers.non_field_errors.0`: no more than 100 elements |
| `EXT-duplicate-in-list` | PATCH network-elements; {"external_identifiers": [{"source": "ERP", "value": "new"}, {"source": "ERP", "value": "new"}], "name": "Attempted edit"} | 400; `external_identifiers.0`: Each source and value pair must be unique. |
| `EXT-already-claimed` | PATCH network-elements; {"external_identifiers": [{"source": "OTHER", "value": "claimed"}], "name": "Attempted edit"} | 400; `external_identifiers.0`: An active identifier with this source and value already exists. |
| `EXT-mixed-incomplete` | PATCH network-elements; {"external_identifiers": [{"source": "ERP", "value": "new"}, {"source": "ERP"}], "name": "Attempted edit"} | 400; `external_identifiers.1.value.0`: This field is required. |
### Geographic validation

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `GEO-location-scalar` | PATCH physical-devices; {"location": "POINT(1 2)"} | 400; `location.0`: Expected WGS84 GeoJSON geometry of type |
| `GEO-location-missing-type` | PATCH physical-devices; {"location": {"coordinates": [1, 2]}} | 400; `location.0`: Expected WGS84 GeoJSON geometry of type |
| `GEO-location-unsupported-type` | PATCH physical-devices; {"location": {"type": "MultiPoint", "coordinates": [[1, 2]]}} | 400; `location.0`: Expected WGS84 GeoJSON geometry of type |
| `GEO-location-crs` | PATCH physical-devices; {"location": {"type": "Point", "coordinates": [1, 2], "crs": null}} | 400; `location.0`: Expected WGS84 GeoJSON geometry of type |
| `GEO-location-missing-coordinates` | PATCH physical-devices; {"location": {"type": "Point"}} | 400; `location.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-location-third-dimension` | PATCH physical-devices; {"location": {"type": "Point", "coordinates": [1, 2, 3]}} | 400; `location.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-location-boolean` | PATCH physical-devices; {"location": {"type": "Point", "coordinates": [true, 2]}} | 400; `location.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-location-text` | PATCH physical-devices; {"location": {"type": "Point", "coordinates": ["1", 2]}} | 400; `location.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-location-longitude` | PATCH physical-devices; {"location": {"type": "Point", "coordinates": [181, 2]}} | 400; `location.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-location-latitude` | PATCH physical-devices; {"location": {"type": "Point", "coordinates": [1, -91]}} | 400; `location.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-location-empty` | PATCH physical-devices; {"location": {"type": "Point", "coordinates": []}} | 400; `location.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-geometry-scalar` | PATCH network-elements; {"geometry": "POINT(1 2)"} | 400; `geometry.0`: Expected WGS84 GeoJSON geometry of type |
| `GEO-geometry-missing-type` | PATCH network-elements; {"geometry": {"coordinates": [1, 2]}} | 400; `geometry.0`: Expected WGS84 GeoJSON geometry of type |
| `GEO-geometry-unsupported-type` | PATCH network-elements; {"geometry": {"type": "MultiPoint", "coordinates": [[1, 2]]}} | 400; `geometry.0`: Expected WGS84 GeoJSON geometry of type |
| `GEO-geometry-crs` | PATCH network-elements; {"geometry": {"type": "Point", "coordinates": [1, 2], "crs": null}} | 400; `geometry.0`: Expected WGS84 GeoJSON geometry of type |
| `GEO-geometry-missing-coordinates` | PATCH network-elements; {"geometry": {"type": "Point"}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-geometry-third-dimension` | PATCH network-elements; {"geometry": {"type": "Point", "coordinates": [1, 2, 3]}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-geometry-boolean` | PATCH network-elements; {"geometry": {"type": "Point", "coordinates": [true, 2]}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-geometry-text` | PATCH network-elements; {"geometry": {"type": "Point", "coordinates": ["1", 2]}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-geometry-longitude` | PATCH network-elements; {"geometry": {"type": "Point", "coordinates": [181, 2]}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-geometry-latitude` | PATCH network-elements; {"geometry": {"type": "Point", "coordinates": [1, -91]}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-geometry-empty` | PATCH network-elements; {"geometry": {"type": "Point", "coordinates": []}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-line-one-point` | PATCH network-elements; {"geometry": {"type": "LineString", "coordinates": [[1, 2]]}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-line-repeated-point` | PATCH network-elements; {"geometry": {"type": "LineString", "coordinates": [[1, 2], [1, 2]]}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-polygon-empty` | PATCH network-elements; {"geometry": {"type": "Polygon", "coordinates": []}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-polygon-short-ring` | PATCH network-elements; {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-polygon-unclosed` | PATCH network-elements; {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
| `GEO-polygon-self-intersection` | PATCH network-elements; {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]}} | 400; `geometry.0`: Provide valid two-dimensional longitude and latitude coordinates in WGS84. |
### Collection configuration

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `CONFIG-array` | PATCH measurements; {"data_collection_config": []} | 400; `data_collection_config.0`: Expected a JSON object. |
| `CONFIG-scalar` | PATCH measurements; {"data_collection_config": "https"} | 400; `data_collection_config.0`: Expected a JSON object. |
| `CONFIG-protocol-long` | PATCH measurements; {"data_collection_config": {"protocol": "ppppppppppppppppppppppppppppppppppppppppppppppppppp"}} | 400; `data_collection_config.protocol.0`: no more than 50 characters |
| `CONFIG-endpoint-long` | PATCH measurements; {"data_collection_config": {"endpoint": "'e' repeated 2049 times"}} | 400; `data_collection_config.endpoint.0`: no more than 2048 characters |
| `CONFIG-source-long` | PATCH measurements; {"data_collection_config": {"source_identifier": "'s' repeated 256 times"}} | 400; `data_collection_config.source_identifier.0`: no more than 255 characters |
| `CONFIG-protocol-object` | PATCH measurements; {"data_collection_config": {"protocol": {}}} | 400; `data_collection_config.protocol.0`: Not a valid string. |
| `CONFIG-protocol-null` | PATCH measurements; {"data_collection_config": {"protocol": null}} | 400; `data_collection_config.protocol.0`: This field may not be null. |
| `CONFIG-extra-array` | PATCH measurements; {"data_collection_config": {"extra_settings": []}} | 400; `data_collection_config.extra_settings.0`: Expected a JSON object. |
| `CONFIG-extra-null` | PATCH measurements; {"data_collection_config": {"extra_settings": null}} | 400; `data_collection_config.extra_settings.0`: This field may not be null. |
| `CONFIG-null-in-value` | PATCH measurements; {"data_collection_config": {"custom": ["bad\u0000value"]}} | 400; `data_collection_config.0`: JSON strings cannot contain null characters. |
| `CONFIG-null-in-key` | PATCH measurements; {"data_collection_config": {"bad\u0000key": "value"}} | 400; `data_collection_config.0`: JSON strings cannot contain null characters. |
| `CONFIG-invalid-unicode` | PATCH measurements; {"data_collection_config": {"custom": "\ud800"}} | 400; `data_collection_config.0`: Expected a valid UTF-8 JSON object. |
### Search and filtering

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `FILTER-physical-devices-department-text` | GET physical-devices; {"department": "abc"} | 400; `department.0`: A valid integer is required. |
| `FILTER-physical-devices-department-fraction` | GET physical-devices; {"department": "1.5"} | 400; `department.0`: A valid integer is required. |
| `FILTER-physical-devices-department-zero` | GET physical-devices; {"department": "0"} | 400; `department.0`: greater than or equal to 1 |
| `FILTER-physical-devices-department-overflow` | GET physical-devices; {"department": "9223372036854775808"} | 400; `department.0`: less than or equal to 9223372036854775807 |
| `FILTER-physical-devices-device_type-text` | GET physical-devices; {"device_type": "abc"} | 400; `device_type.0`: A valid integer is required. |
| `FILTER-physical-devices-device_type-fraction` | GET physical-devices; {"device_type": "1.5"} | 400; `device_type.0`: A valid integer is required. |
| `FILTER-physical-devices-device_type-zero` | GET physical-devices; {"device_type": "0"} | 400; `device_type.0`: greater than or equal to 1 |
| `FILTER-physical-devices-device_type-overflow` | GET physical-devices; {"device_type": "9223372036854775808"} | 400; `device_type.0`: less than or equal to 9223372036854775807 |
| `FILTER-network-elements-department-text` | GET network-elements; {"department": "abc"} | 400; `department.0`: A valid integer is required. |
| `FILTER-network-elements-department-fraction` | GET network-elements; {"department": "1.5"} | 400; `department.0`: A valid integer is required. |
| `FILTER-network-elements-department-zero` | GET network-elements; {"department": "0"} | 400; `department.0`: greater than or equal to 1 |
| `FILTER-network-elements-department-overflow` | GET network-elements; {"department": "9223372036854775808"} | 400; `department.0`: less than or equal to 9223372036854775807 |
| `FILTER-network-elements-element_type-text` | GET network-elements; {"element_type": "abc"} | 400; `element_type.0`: A valid integer is required. |
| `FILTER-network-elements-element_type-fraction` | GET network-elements; {"element_type": "1.5"} | 400; `element_type.0`: A valid integer is required. |
| `FILTER-network-elements-element_type-zero` | GET network-elements; {"element_type": "0"} | 400; `element_type.0`: greater than or equal to 1 |
| `FILTER-network-elements-element_type-overflow` | GET network-elements; {"element_type": "9223372036854775808"} | 400; `element_type.0`: less than or equal to 9223372036854775807 |
| `FILTER-measurements-department-text` | GET measurements; {"department": "abc"} | 400; `department.0`: A valid integer is required. |
| `FILTER-measurements-department-fraction` | GET measurements; {"department": "1.5"} | 400; `department.0`: A valid integer is required. |
| `FILTER-measurements-department-zero` | GET measurements; {"department": "0"} | 400; `department.0`: greater than or equal to 1 |
| `FILTER-measurements-department-overflow` | GET measurements; {"department": "9223372036854775808"} | 400; `department.0`: less than or equal to 9223372036854775807 |
| `FILTER-measurements-physical_device-text` | GET measurements; {"physical_device": "abc"} | 400; `physical_device.0`: A valid integer is required. |
| `FILTER-measurements-physical_device-fraction` | GET measurements; {"physical_device": "1.5"} | 400; `physical_device.0`: A valid integer is required. |
| `FILTER-measurements-physical_device-zero` | GET measurements; {"physical_device": "0"} | 400; `physical_device.0`: greater than or equal to 1 |
| `FILTER-measurements-physical_device-overflow` | GET measurements; {"physical_device": "9223372036854775808"} | 400; `physical_device.0`: less than or equal to 9223372036854775807 |
| `FILTER-measurements-network_element-text` | GET measurements; {"network_element": "abc"} | 400; `network_element.0`: A valid integer is required. |
| `FILTER-measurements-network_element-fraction` | GET measurements; {"network_element": "1.5"} | 400; `network_element.0`: A valid integer is required. |
| `FILTER-measurements-network_element-zero` | GET measurements; {"network_element": "0"} | 400; `network_element.0`: greater than or equal to 1 |
| `FILTER-measurements-network_element-overflow` | GET measurements; {"network_element": "9223372036854775808"} | 400; `network_element.0`: less than or equal to 9223372036854775807 |
| `FILTER-measurements-measurement_type-text` | GET measurements; {"measurement_type": "abc"} | 400; `measurement_type.0`: A valid integer is required. |
| `FILTER-measurements-measurement_type-fraction` | GET measurements; {"measurement_type": "1.5"} | 400; `measurement_type.0`: A valid integer is required. |
| `FILTER-measurements-measurement_type-zero` | GET measurements; {"measurement_type": "0"} | 400; `measurement_type.0`: greater than or equal to 1 |
| `FILTER-measurements-measurement_type-overflow` | GET measurements; {"measurement_type": "9223372036854775808"} | 400; `measurement_type.0`: less than or equal to 9223372036854775807 |
| `FILTER-measurements-measurement_unit-text` | GET measurements; {"measurement_unit": "abc"} | 400; `measurement_unit.0`: A valid integer is required. |
| `FILTER-measurements-measurement_unit-fraction` | GET measurements; {"measurement_unit": "1.5"} | 400; `measurement_unit.0`: A valid integer is required. |
| `FILTER-measurements-measurement_unit-zero` | GET measurements; {"measurement_unit": "0"} | 400; `measurement_unit.0`: greater than or equal to 1 |
| `FILTER-measurements-measurement_unit-overflow` | GET measurements; {"measurement_unit": "9223372036854775808"} | 400; `measurement_unit.0`: less than or equal to 9223372036854775807 |
| `FILTER-physical-devices-bbox-arity` | GET physical-devices; {"bbox": "1,2,3"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-physical-devices-bbox-text` | GET physical-devices; {"bbox": "a,b,c,d"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-physical-devices-bbox-longitude` | GET physical-devices; {"bbox": "-181,0,1,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-physical-devices-bbox-latitude` | GET physical-devices; {"bbox": "0,-91,1,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-physical-devices-bbox-reversed` | GET physical-devices; {"bbox": "2,0,1,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-physical-devices-bbox-zero-height` | GET physical-devices; {"bbox": "0,1,2,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-physical-devices-bbox-nan` | GET physical-devices; {"bbox": "nan,0,1,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-physical-devices-bbox-infinity` | GET physical-devices; {"bbox": "0,0,inf,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-network-elements-bbox-arity` | GET network-elements; {"bbox": "1,2,3"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-network-elements-bbox-text` | GET network-elements; {"bbox": "a,b,c,d"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-network-elements-bbox-longitude` | GET network-elements; {"bbox": "-181,0,1,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-network-elements-bbox-latitude` | GET network-elements; {"bbox": "0,-91,1,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-network-elements-bbox-reversed` | GET network-elements; {"bbox": "2,0,1,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-network-elements-bbox-zero-height` | GET network-elements; {"bbox": "0,1,2,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-network-elements-bbox-nan` | GET network-elements; {"bbox": "nan,0,1,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-network-elements-bbox-infinity` | GET network-elements; {"bbox": "0,0,inf,1"} | 400; `bbox`: Expected west,south,east,north in WGS84 with increasing coordinates. |
| `FILTER-identifier-blank` | GET network-elements; {"identifier": ""} | 400; `identifier.0`: This field may not be blank. |
| `FILTER-identifier-long` | GET network-elements; {"identifier": "'x' repeated 256 times"} | 400; `identifier.0`: no more than 255 characters |
### Controlled lists

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `CATALOG-physical-device-types-duplicate` | POST physical-device-types; {"name": "$duplicate_device_type"}; actor=catalog-manager | 400; `name.0`: An active entry already has this name. |
| `CATALOG-physical-device-types-history-flag` | GET physical-device-types; {"include_inactive": "maybe"} | 400; `include_inactive.0`: Must be a valid boolean. |
| `CATALOG-network-element-types-duplicate` | POST network-element-types; {"name": "$duplicate_element_type"}; actor=catalog-manager | 400; `name.0`: An active entry already has this name. |
| `CATALOG-network-element-types-history-flag` | GET network-element-types; {"include_inactive": "maybe"} | 400; `include_inactive.0`: Must be a valid boolean. |
| `CATALOG-measurement-types-duplicate` | POST measurement-types; {"name": "$duplicate_measurement_type"}; actor=catalog-manager | 400; `name.0`: An active entry already has this name. |
| `CATALOG-measurement-types-history-flag` | GET measurement-types; {"include_inactive": "maybe"} | 400; `include_inactive.0`: Must be a valid boolean. |
| `CATALOG-measurement-units-duplicate` | POST measurement-units; {"name": "$duplicate_measurement_unit"}; actor=catalog-manager | 400; `name.0`: An active entry already has this name. |
| `CATALOG-measurement-units-history-flag` | GET measurement-units; {"include_inactive": "maybe"} | 400; `include_inactive.0`: Must be a valid boolean. |
### Logical deletion

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `DELETE-physical-devices-dependency` | DELETE physical-devices; {} | 409; `detail`: Archive the active records that reference this record first. |
| `DELETE-network-elements-dependency` | DELETE network-elements; {} | 409; `detail`: Archive the active records that reference this record first. |
| `DELETE-physical-device-types-dependency` | DELETE physical-device-types; {}; actor=catalog-manager | 409; `detail`: Archive the active records that reference this record first. |
| `DELETE-network-element-types-dependency` | DELETE network-element-types; {}; actor=catalog-manager | 409; `detail`: Archive the active records that reference this record first. |
| `DELETE-measurement-types-dependency` | DELETE measurement-types; {}; actor=catalog-manager | 409; `detail`: Archive the active records that reference this record first. |
| `DELETE-measurement-units-dependency` | DELETE measurement-units; {}; actor=catalog-manager | 409; `detail`: Archive the active records that reference this record first. |
### Authentication and permissions

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `AUTH-physical-devices-anonymous` | GET physical-devices; {}; actor=anonymous | 403; `detail`: Authentication credentials were not provided. |
| `AUTH-physical-devices-unavailable-department` | POST physical-devices; {"department": 999}; setup=missing-department | 403; `detail`: This department is unavailable. |
| `AUTH-network-elements-anonymous` | GET network-elements; {}; actor=anonymous | 403; `detail`: Authentication credentials were not provided. |
| `AUTH-network-elements-unavailable-department` | POST network-elements; {"department": 999}; setup=missing-department | 403; `detail`: This department is unavailable. |
| `AUTH-measurements-anonymous` | GET measurements; {}; actor=anonymous | 403; `detail`: Authentication credentials were not provided. |
| `AUTH-measurements-unavailable-department` | POST measurements; {"department": 999}; setup=missing-department | 403; `detail`: This department is unavailable. |
| `AUTH-shared-lists-no-platform` | POST measurement-types; {}; setup=no-platform; actor=catalog-manager | 403; `detail`: You do not have write access to the shared lists. |
### HTTP methods

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `METHOD-physical-devices-PUT` | PUT physical-devices; {}; setup=collection | 405; `detail`: Method "PUT" not allowed. |
| `METHOD-physical-devices-POST` | POST physical-devices; {}; setup=detail | 405; `detail`: Method "POST" not allowed. |
| `METHOD-imports-excel-GET` | GET imports/excel; {}; setup=collection | 405; `detail`: Method "GET" not allowed. |
### Pagination

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `PAGE-not-a-page` | GET physical-devices; {"page": "not-a-page"} | 404; `detail`: Invalid page. |
| `PAGE-0` | GET physical-devices; {"page": "0"} | 404; `detail`: Invalid page. |
| `PAGE-999999` | GET physical-devices; {"page": "999999"} | 404; `detail`: Invalid page. |
### Collection configuration

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `CONFIG-nonfinite-number` | PATCH measurements; {"data_collection_config": {"custom": "raw JSON number 1e999"}}; setup=nonfinite-config | 400; `data_collection_config.0`: Expected a valid UTF-8 JSON object. |
### Request parsing

| Case ID / pytest parameter | Request / precondition | Expected HTTP and error |
| --- | --- | --- |
| `HTTP-malformed-json` | POST physical-devices; {}; setup=malformed-json | 400; `detail`: JSON parse error |

## Excel errors

Each ID is a separate parameter of `test_import_error_contract`. The JSON catalog records the observed sheet and Excel row number. All cases preserve the complete database snapshot. The unresolved-reference and incomplete-identifier cases deliberately include an earlier valid row to prove whole-workbook rollback.

| Case ID | Input / precondition | Expected HTTP and error |
| --- | --- | --- |
| `XLSX-missing-file` | Missing file (`missing-file` fixture) | 400; No file was submitted. |
| `XLSX-empty-file` | Empty upload (`empty-file` fixture) | 400; The submitted file is empty. |
| `XLSX-missing-department` | Missing department (`missing-department` fixture) | 400; This field is required. |
| `XLSX-invalid-department` | Invalid department (`invalid-department` fixture) | 400; A valid integer is required. |
| `XLSX-suffix` | Wrong extension (`suffix` fixture) | 400; Upload an .xlsx workbook of up to 5 MiB. |
| `XLSX-upload-limit` | More than 5 MiB uploaded (`upload-limit` fixture) | 400; Upload an .xlsx workbook of up to 5 MiB. |
| `XLSX-zip-count` | More than 200 ZIP members (`zip-count` fixture) | 400; The workbook expands beyond the import limit. |
| `XLSX-expanded-limit` | More than 25 MiB expanded (`expanded-limit` fixture) | 400; The workbook expands beyond the import limit. |
| `XLSX-macro` | VBA member in uploaded workbook (`macro` fixture) | 400; Upload an .xlsx workbook without macros. |
| `XLSX-corrupt-zip` | Unreadable ZIP (`corrupt-zip` fixture) | 400; The file could not be read as an .xlsx workbook. |
| `XLSX-malformed-xml` | Malformed worksheet XML (`malformed-xml` fixture) | 400; The file could not be read as an .xlsx workbook. |
| `XLSX-corrupt-deflate` | Corrupt compressed member (`corrupt-deflate` fixture) | 400; The file could not be read as an .xlsx workbook. |
| `XLSX-unknown-sheet` | Unknown worksheet (`unknown-sheet` fixture) | 400; Unknown worksheet. |
| `XLSX-empty` | No metadata rows (`empty` fixture) | 400; The workbook has no metadata rows. |
| `XLSX-header-missing` | Missing required header (`header-missing` fixture) | 400; Use unique columns |
| `XLSX-header-duplicate` | Duplicate header (`header-duplicate` fixture) | 400; Use unique columns |
| `XLSX-header-unknown` | Unknown header (`header-unknown` fixture) | 400; Use unique columns |
| `XLSX-header-blank` | Blank interior header (`header-blank` fixture) | 400; Use unique columns |
| `XLSX-extra-cell` | Data without a column heading (`extra-cell` fixture) | 400; Every value needs a column heading. |
| `XLSX-formula` | Formula cell (`formula` fixture) | 400; Use literal values without formulas or Excel errors. |
| `XLSX-excel-error` | Excel error cell (`excel-error` fixture) | 400; Use literal values without formulas or Excel errors. |
| `XLSX-ref-format` | Invalid reference grammar (`ref-format` fixture) | 400; Use 1 to 64 letters |
| `XLSX-ref-long` | Reference longer than 64 (`ref-long` fixture) | 400; Use 1 to 64 letters |
| `XLSX-ref-number` | Numeric reference (`ref-number` fixture) | 400; Use 1 to 64 letters |
| `XLSX-ref-duplicate` | Duplicate reference in one sheet (`ref-duplicate` fixture) | 400; This reference already appears on the sheet. |
| `XLSX-row-limit` | Data at Excel row 2002 (`row-limit` fixture) | 400; Use at most 2000 rows per sheet. |
| `XLSX-unresolved-device` | Unresolved Device @ref (`unresolved-device` fixture) | 400; This workbook reference could not be resolved. |
| `XLSX-unresolved-element` | Unresolved Network Element @ref (`unresolved-element` fixture) | 400; This workbook reference could not be resolved. |
| `XLSX-identifier-missing-value` | Incomplete identifier after an earlier valid row (`identifier-missing-value` fixture) | 400; This field is required. |
| `XLSX-json-location` | Invalid JSON text in location (`json:Physical Devices:location` fixture) | 400; Enter valid JSON as text. |
| `XLSX-json-geometry` | Invalid JSON text in geometry (`json:Network Elements:geometry` fixture) | 400; Enter valid JSON as text. |
| `XLSX-json-external_identifiers` | Invalid JSON text in external_identifiers (`json:Network Elements:external_identifiers` fixture) | 400; Enter valid JSON as text. |
| `XLSX-json-data_collection_config` | Invalid JSON text in data_collection_config (`json:Measurements:data_collection_config` fixture) | 400; Enter valid JSON as text. |

Excel limits are 5 MiB uploaded, 25 MiB expanded, 200 ZIP members and 2000 worksheet rows below the header. Blank gaps count towards the last row position; row 2002 is rejected. Header-only sheets do not import records. These are current implementation limits, not newly introduced features.

## Database and command errors

| Case ID | Operation | Expected failure and preservation |
| --- | --- | --- |
| `DB-measurement-physical_device-required` | Measurement NOT NULL physical_device | SQLSTATE 23502; unchanged metadata |
| `DB-measurement-network_element-required` | Measurement NOT NULL network_element | SQLSTATE 23502; unchanged metadata |
| `DB-measurement-measurement_type-required` | Measurement NOT NULL measurement_type | SQLSTATE 23502; unchanged metadata |
| `DB-measurement-measurement_unit-required` | Measurement NOT NULL measurement_unit | SQLSTATE 23502; unchanged metadata |
| `DB-measurement-physical_device-fk` | Measurement foreign key physical_device | SQLSTATE 23503; unchanged metadata |
| `DB-measurement-network_element-fk` | Measurement foreign key network_element | SQLSTATE 23503; unchanged metadata |
| `DB-measurement-measurement_type-fk` | Measurement foreign key measurement_type | SQLSTATE 23503; unchanged metadata |
| `DB-measurement-measurement_unit-fk` | Measurement foreign key measurement_unit | SQLSTATE 23503; unchanged metadata |
| `DB-physical-device-types-active-name` | Case-insensitive active catalog uniqueness: physical-device-types | SQLSTATE 23505; unchanged metadata |
| `DB-network-element-types-active-name` | Case-insensitive active catalog uniqueness: network-element-types | SQLSTATE 23505; unchanged metadata |
| `DB-measurement-types-active-name` | Case-insensitive active catalog uniqueness: measurement-types | SQLSTATE 23505; unchanged metadata |
| `DB-measurement-units-active-name` | Case-insensitive active catalog uniqueness: measurement-units | SQLSTATE 23505; unchanged metadata |
| `DB-device-location-type` | PostGIS Point typmod rejects a LineString | SQLSTATE 22023; unchanged metadata |
| `DB-device-location-srid` | PostGIS SRID typmod rejects 3857 | SQLSTATE 22023; unchanged metadata |
| `CLI-suffix` | Wrong destination suffix | CommandError: Use an .xlsx destination.; existing files unchanged |
| `CLI-existing` | Existing destination without --force | CommandError: Destination already exists. Use --force to replace it.; existing files unchanged |
| `CLI-parent` | Missing destination directory | CommandError: The destination directory must exist.; existing files unchanged |
| `CLI-write` | Filesystem refuses workbook write | CommandError: Could not write the workbook:; existing files unchanged |

## Positive, boundary and existing integration coverage

| Test | Expected behavior |
| --- | --- |
| `test_session_csrf_error_preserves_metadata` | Actual Django session: missing CSRF returns 403 with unchanged metadata; matching cookie/header permits creation (201). |
| `test_import_requires_multipart_and_preserves_metadata` | JSON request to the multipart-only endpoint returns 415 with unchanged metadata. |
| `test_pagination_fallback_is_not_an_error` (four parameters) | Invalid/zero/negative page size defaults to 25; 1000 caps at 100. Unknown ordering is ignored; results retain stable ID ordering. |
| `test_config_and_geometry_valid_boundaries` | Accept longitude/latitude endpoints; exact config string limits and arbitrary JSON keys persist; optional config can be null. |
| `test_external_identifiers_accept_exact_limits_and_preserve_retained_id` | Accept exactly 100 identifiers, source length 120 and value length 255; retain the existing identifier's ID. |
| `test_read_only_audit_fields_ignore_client_values` | Submitted ID, actor, timestamp and is_active fields are ignored; the backend assigns the actual actor/time and active status. |
| `test_workbook_row_boundary_and_command_force` | Generate all three sheets; --force replaces the file; exactly 2000 data rows parse successfully. |
| Existing `test_linked_crud_archival_and_dependencies` | Create/read/update/archive all three domains; six dependency conflicts; protected physical deletion and audit actors. |
| Existing identifier PATCH/history tests | Valid/omitted/empty lists, missing source/value/mixed list, stable retained IDs, archived history and atomic rejection. |
| Existing scope/default-deny/catalog tests | Read-only 403 on PATCH/DELETE across three domains; out-of-scope details 404; default deny, scoped search, catalog management and historical references. |
| Existing PostGIS/constraint tests | Cross-Department composite foreign keys, unsupported Network geometry and Department-scoped active external-system identifier uniqueness. |
| Existing Excel workflows | Linked three-domain import, generated example, optional accounts/config, wrong-Department references, late invalid row and duplicate identifier rollback. |
| Existing four concurrency tests | Measurement creation waits for Device/catalog archive; racing identifier API/import writers in one Department receive 400 and preserve integrity. |
| `core/tests/test_health.py`, `core/tests/test_database.py` | GET health status/JSON and actual PostGIS engine/extension query. |

Exact existing names and node IDs are in the JUnit report and [acceptance mapping](argyris-backend-validation.md).

## Reproduced defect and scope limits

`XLSX-corrupt-deflate` first reproduced an uncaught `zlib.error` and HTTP 500. The only production change in the 14 November error audit adds that concrete decompression exception to the existing unreadable-workbook handler. It now returns the existing file error with HTTP 400. No endpoint, schema, migration, frontend or CI workflow changed.

FixturePolicy supplies synthetic scopes through the existing adapter. This catalog verifies backend enforcement, an actual Django session/CSRF exchange and default-deny behavior; it does not implement or certify the team's future login endpoint, API keys, production User-Department membership or role adapter. The Department integration decision remains in the [shared handover](../development/pr27-shared-integration.md). Unexpected server/database outages and an invalid administrator-supplied adapter path are operational failures, not invented client 400 responses. The suite exercises the enumerated contracts and boundaries; it is not a claim to test every possible file or third-party library exception.
