from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("platform_security", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=models.CASCADE,
                        related_name="platform_role",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("VIEWER", "Viewer"),
                            ("EDITOR", "Editor"),
                            ("DEPARTMENT_ADMIN", "Department Administrator"),
                            ("SYSTEM_ADMIN", "System Administrator"),
                        ],
                        max_length=16,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(role__in=("VIEWER", "EDITOR", "DEPARTMENT_ADMIN", "SYSTEM_ADMIN")),
                        name="platform_security_user_role_valid",
                    ),
                ],
            },
        ),
    ]
