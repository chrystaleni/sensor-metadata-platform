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


class UserRole(models.Model):
    class Role(models.TextChoices):
        VIEWER = "VIEWER", "Viewer"
        EDITOR = "EDITOR", "Editor"
        DEPARTMENT_ADMIN = "DEPARTMENT_ADMIN", "Department Administrator"
        SYSTEM_ADMIN = "SYSTEM_ADMIN", "System Administrator"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="platform_role",
    )
    role = models.CharField(max_length=16, choices=Role.choices)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=("VIEWER", "EDITOR", "DEPARTMENT_ADMIN", "SYSTEM_ADMIN")),
                name="platform_security_user_role_valid",
            ),
        ]


class LoginAttemptWindow(models.Model):
    client_key = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveIntegerField()
    expires_at = models.DateTimeField(db_index=True)
