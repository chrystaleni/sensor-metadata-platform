import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_organisation_migration_preserves_existing_departments():
    before = [("local_departments", "0001_initial")]
    after = [("local_departments", "0002_organisation_department_organisation")]
    executor = MigrationExecutor(connection)
    original_targets = executor.loader.graph.leaf_nodes()

    try:
        executor.migrate(before)
        old_apps = executor.loader.project_state(before).apps
        old_department = old_apps.get_model("local_departments", "Department")
        old_department.objects.create(id=41, name="North")
        old_department.objects.create(id=83, name="South")

        executor = MigrationExecutor(connection)
        executor.migrate(after)
        new_apps = executor.loader.project_state(after).apps
        department = new_apps.get_model("local_departments", "Department")

        assert list(department.objects.order_by("id").values_list(
            "id", "name", "organisation_id"
        )) == [(41, "North", None), (83, "South", None)]

        unassigned = department.objects.create(name="Unassigned")
        unassigned.refresh_from_db()
        assert unassigned.organisation_id is None
    finally:
        MigrationExecutor(connection).migrate(original_targets)
