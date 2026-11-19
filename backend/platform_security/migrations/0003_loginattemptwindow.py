from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("platform_security", "0002_userrole")]

    operations = [
        migrations.CreateModel(
            name="LoginAttemptWindow",
            fields=[
                ("client_key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("failures", models.PositiveIntegerField()),
                ("expires_at", models.DateTimeField(db_index=True)),
            ],
        ),
    ]
