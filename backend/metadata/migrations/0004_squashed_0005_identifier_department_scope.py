from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0003_externalidentifier_created_by_and_more"),
        migrations.swappable_dependency(settings.METADATA_DEPARTMENT_MODEL),
    ]

    replaces = [
        ("metadata", "0004_identifier_system_uniqueness"),
        ("metadata", "0005_identifier_department_scope"),
    ]

    operations = [
        migrations.AddField(
            model_name="externalidentifier",
            name="department",
            field=models.ForeignKey(
                to=settings.METADATA_DEPARTMENT_MODEL, null=True, editable=False,
                on_delete=django.db.models.deletion.PROTECT, related_name="+",
            ),
        ),
        # Backfill all rows, including archived identifiers, without changing
        # primary keys, source/value strings, timestamps or attribution.
        migrations.RunSQL(
            """
            UPDATE metadata_externalidentifier AS identifier
            SET department_id = element.department_id
            FROM metadata_networkelement AS element
            WHERE identifier.network_element_id = element.id
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name="externalidentifier",
            name="department",
            field=models.ForeignKey(
                to=settings.METADATA_DEPARTMENT_MODEL, editable=False,
                on_delete=django.db.models.deletion.PROTECT, related_name="+",
            ),
        ),
        migrations.AddConstraint(
            model_name="externalidentifier",
            constraint=models.UniqueConstraint(
                fields=("department", "source", "value"),
                condition=models.Q(deleted_at__isnull=True),
                name="meta_active_dept_external_identifier",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="externalidentifier", name="meta_active_external_identifier",
        ),
        migrations.RunSQL(
            """
            ALTER TABLE metadata_externalidentifier
            ADD CONSTRAINT meta_identifier_element_department
            FOREIGN KEY (department_id, network_element_id)
            REFERENCES metadata_networkelement (department_id, id)
            """,
            reverse_sql=(
                "ALTER TABLE metadata_externalidentifier "
                "DROP CONSTRAINT meta_identifier_element_department"
            ),
        ),
    ]
