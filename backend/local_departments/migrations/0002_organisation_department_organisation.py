import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("local_departments", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Organisation",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("code", models.CharField(max_length=120, unique=True)),
            ],
        ),
        migrations.AddField(
            model_name="department",
            name="organisation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="departments",
                to="local_departments.organisation",
            ),
        ),
    ]
