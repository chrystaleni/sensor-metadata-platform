import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = ("metadata", "0005_identifier_department_scope")
AFTER = ("metadata", "0006_data_collection_configuration")
DEPARTMENTS = ("local_departments", "0004_require_department_organisation")


def test_configurations_move_to_their_own_entity_and_back(transactional_db):
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate([BEFORE, DEPARTMENTS])
        old = executor.loader.project_state([BEFORE, DEPARTMENTS]).apps
        Organisation = old.get_model("local_departments", "Organisation")
        Department = old.get_model("local_departments", "Department")
        organisation = Organisation.objects.create(code="mig", name="Mig")
        department = Department.objects.create(name="North", organisation=organisation)
        shared = Department.objects.create(name="Platform", organisation=organisation)

        def make(name, model, **extra):
            return old.get_model("metadata", model).objects.create(name=name, department_id=extra.pop("dept", department.pk), **extra)

        device_type = make("dt", "PhysicalDeviceType", dept=shared.pk)
        element_type = make("et", "NetworkElementType", dept=shared.pk)
        m_type = make("mt", "MeasurementType", dept=shared.pk)
        unit = make("u", "MeasurementUnit", dept=shared.pk, symbol="x")
        device = make("d", "PhysicalDevice", device_type_id=device_type.pk)
        element = make("e", "NetworkElement", element_type_id=element_type.pk)
        Measurement = old.get_model("metadata", "Measurement")
        common = dict(department_id=department.pk, physical_device_id=device.pk, network_element_id=element.pk,
                      measurement_type_id=m_type.pk, measurement_unit_id=unit.pk)
        with_config = Measurement.objects.create(name="with", data_collection_config={"protocol": "mqtt"}, **common)
        without = Measurement.objects.create(name="without", **common)

        executor = MigrationExecutor(connection)
        executor.migrate([AFTER, DEPARTMENTS])
        new = executor.loader.project_state([AFTER, DEPARTMENTS]).apps
        Configuration = new.get_model("metadata", "DataCollectionConfiguration")
        rows = list(Configuration.objects.values("measurement_id", "department_id", "config"))
        assert rows == [{"measurement_id": with_config.pk, "department_id": department.pk, "config": {"protocol": "mqtt"}}]
        assert without.pk not in {r["measurement_id"] for r in rows}
        assert not any(f.name == "data_collection_config" for f in new.get_model("metadata", "Measurement")._meta.fields)

        executor = MigrationExecutor(connection)
        executor.migrate([BEFORE, DEPARTMENTS])
        back = executor.loader.project_state([BEFORE, DEPARTMENTS]).apps.get_model("metadata", "Measurement")
        assert back.objects.get(pk=with_config.pk).data_collection_config == {"protocol": "mqtt"}
        assert back.objects.get(pk=without.pk).data_collection_config is None
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(leaves)
