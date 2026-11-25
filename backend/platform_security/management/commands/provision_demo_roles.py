from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from local_departments.models import Department, Organisation
from metadata.platform import PLATFORM_CODE
from platform_security.models import UserRole


class Command(BaseCommand):
    help = "Create three local demo accounts and prompt for their passwords."

    def add_arguments(self, parser):
        parser.add_argument("--organisation-code", required=True)
        parser.add_argument("--organisation-name", required=True)
        parser.add_argument("--department-name", required=True, help="Department for the two scoped roles.")
        parser.add_argument("--viewer", required=True, help="Username for the Viewer.")
        parser.add_argument("--department-admin", required=True, help="Username for the Department Administrator.")
        parser.add_argument("--system-admin", required=True, help="Username for the System Administrator.")

    def handle(
        self, organisation_code, organisation_name, department_name,
        viewer, department_admin, system_admin, **options,
    ):
        user_model = get_user_model()
        roles = (
            (UserRole.Role.VIEWER, viewer),
            (UserRole.Role.DEPARTMENT_ADMIN, department_admin),
            (UserRole.Role.SYSTEM_ADMIN, system_admin),
        )
        accounts = [(role, user_model.normalize_username(name.strip())) for role, name in roles]
        usernames = {username for _, username in accounts}
        if len(usernames) != len(accounts):
            raise CommandError("Choose a distinct username for each role.")

        organisation = Organisation(code=organisation_code.strip(), name=organisation_name.strip())
        if organisation.code == PLATFORM_CODE:
            raise CommandError("Choose a business Organisation code. The Platform Organisation owns the shared catalogs.")

        try:
            organisation.full_clean(validate_unique=False)
            department_name = Department._meta.get_field("name").clean(department_name.strip(), None)
            username_field = user_model._meta.get_field(user_model.USERNAME_FIELD)
            for _, username in accounts:
                username_field.clean(username, None)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error

        with transaction.atomic():
            if user_model.objects.filter(username__in=usernames).exists():
                raise CommandError("Choose three available usernames.")

            stored_organisation, _ = Organisation.objects.get_or_create(
                code=organisation.code, defaults={"name": organisation.name},
            )
            if stored_organisation.name != organisation.name:
                raise CommandError("That Organisation code already belongs to a different name.")

            department, _ = Department.objects.get_or_create(
                organisation=stored_organisation, name=department_name,
            )
            command_output = StringIO()
            for role, username in accounts:
                self.stdout.write(f"Set the password for {username} ({role.label}).")
                departments = [] if role == UserRole.Role.SYSTEM_ADMIN else [department.pk]
                call_command(
                    "configure_platform_user", username, create=True, role=role,
                    department=departments, stdout=command_output,
                )

        self.stdout.write(self.style.SUCCESS(
            f"Created three accounts. The Viewer and Department Administrator belong to Department {department.pk}."
        ))
