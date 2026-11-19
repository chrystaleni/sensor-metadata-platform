import django.db.models.deletion
from django.db import migrations, models


def require_assigned_departments(apps, schema_editor):
    department = apps.get_model("local_departments", "Department")
    unassigned = department.objects.using(schema_editor.connection.alias).filter(organisation__isnull=True)
    missing_ids = list(unassigned.order_by("pk").values_list("pk", flat=True)[:10])
    if missing_ids:
        raise ValueError(
            "Cannot require Department Organisation ownership while unassigned Departments exist. "
            f"First unassigned Department IDs: {missing_ids}. "
            "Assign each remaining Department to its approved Organisation before retrying."
        )


class Migration(migrations.Migration):
    dependencies = [("local_departments", "0003_backfill_department_organisations")]

    operations = [
        migrations.RunPython(require_assigned_departments, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name="department",
            name="organisation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="departments",
                to="local_departments.organisation",
            ),
        ),
        migrations.AddConstraint(
            model_name="department",
            constraint=models.UniqueConstraint(
                fields=("organisation", "name"), name="local_department_organisation_name_uniq"
            ),
        ),
        migrations.AlterField(
            model_name="department",
            name="name",
            field=models.CharField(max_length=120),
        ),
    ]
