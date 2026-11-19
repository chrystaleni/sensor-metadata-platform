import getpass
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from local_departments.models import Department
from platform_security.models import UserDepartment, UserRole


class Command(BaseCommand):
    help = "Operator provisioning: explicitly assign a role and add existing Department memberships."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--role", required=True, choices=UserRole.Role.values)
        parser.add_argument("--department", action="append", type=int, default=[])
        parser.add_argument("--create", action="store_true")

    @transaction.atomic
    def handle(self, username, role, department, create, **options):
        identifiers = set(department)
        if len(identifiers) != Department.objects.filter(pk__in=identifiers).count():
            raise CommandError("Every Department ID must already exist. Nothing was changed.")
        users = get_user_model().objects
        if create:
            if users.filter(username=username).exists():
                raise CommandError("User exists; omit --create to configure the existing user.")
            user = get_user_model()(username=username)
            password = getpass.getpass("New password: ")
            if password != getpass.getpass("Confirm password: "):
                raise CommandError("Passwords do not match.")
            if len(password) < 12:
                raise CommandError("Use at least 12 characters.")
            try:
                validate_password(password, user)
            except ValidationError as error:
                raise CommandError("; ".join(error.messages)) from error
            user.set_password(password)
            user.full_clean()
            user.save()
        else:
            try:
                user = users.get(username=username)
            except get_user_model().DoesNotExist as error:
                raise CommandError("User does not exist. Use --create for a new user.") from error
        UserRole.objects.update_or_create(user=user, defaults={"role": role})
        for identifier in identifiers:
            UserDepartment.objects.get_or_create(user=user, department_id=identifier)
        self.stdout.write("Role configured; memberships added. Existing memberships were preserved.")
