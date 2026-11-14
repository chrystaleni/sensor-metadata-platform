from django.conf import settings
from django.db import models


class UserDepartment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="department_memberships",
    )
    department = models.ForeignKey(
        "local_departments.Department",
        on_delete=models.PROTECT,
        related_name="user_memberships",
        swappable=False,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "department"),
                name="platform_security_user_department_uniq",
            ),
        ]
