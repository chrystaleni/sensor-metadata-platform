from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                """
                ALTER TABLE metadata_measurement ADD CONSTRAINT meta_measurement_device_department
                FOREIGN KEY (department_id, physical_device_id)
                REFERENCES metadata_physicaldevice (department_id, id)
                """,
                """
                ALTER TABLE metadata_measurement ADD CONSTRAINT meta_measurement_element_department
                FOREIGN KEY (department_id, network_element_id)
                REFERENCES metadata_networkelement (department_id, id)
                """,
            ],
            reverse_sql=[
                "ALTER TABLE metadata_measurement DROP CONSTRAINT meta_measurement_element_department",
                "ALTER TABLE metadata_measurement DROP CONSTRAINT meta_measurement_device_department",
            ],
        ),
    ]
