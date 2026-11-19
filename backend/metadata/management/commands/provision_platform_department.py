from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from local_departments.models import Department, Organisation
from metadata.platform import PLATFORM_CODE, PLATFORM_NAME, catalogs_belong_to


class Command(BaseCommand):
    help = "Provision the shared catalog owner and print its METADATA_PLATFORM_DEPARTMENT_ID."

    @transaction.atomic
    def handle(self, *args, **options):
        organisation, _ = Organisation.objects.select_for_update().get_or_create(
            code=PLATFORM_CODE, defaults={"name": PLATFORM_NAME},
        )
        if organisation.name != PLATFORM_NAME:
            raise CommandError("Organisation code 'platform' already has a different name.")

        departments = list(organisation.departments.select_for_update().order_by("pk")[:2])
        if len(departments) > 1:
            raise CommandError("Multiple Departments belong to Organisation 'platform'. Resolve ownership before provisioning.")

        department = departments[0] if departments else None
        department_id = department.pk if department else None
        configured_id = settings.METADATA_PLATFORM_DEPARTMENT_ID
        if configured_id is not None and configured_id != department_id:
            raise CommandError("METADATA_PLATFORM_DEPARTMENT_ID does not match the existing Platform Department.")
        if not catalogs_belong_to(department_id):
            raise CommandError("Existing controlled lists have conflicting Department ownership. No records were moved.")
        if department is None:
            department = Department.objects.create(organisation=organisation, name=PLATFORM_NAME)

        self.stdout.write(f"METADATA_PLATFORM_DEPARTMENT_ID={department.pk}")
