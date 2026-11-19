from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("local_departments", "0004_require_department_organisation"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserDepartment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="department_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        on_delete=models.PROTECT,
                        related_name="user_memberships",
                        swappable=False,
                        to="local_departments.department",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "department"),
                        name="platform_security_user_department_uniq",
                    ),
                ],
            },
        ),
    ]
