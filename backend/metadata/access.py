from django.conf import settings
from django.utils.module_loading import import_string


class NoAccessPolicy:
    """Interface for the team's authorization adapter. Missing access means deny."""

    def readable_department_ids(self, request):
        return ()

    def writable_department_ids(self, request):
        return ()

    def can_manage_controlled_lists(self, request):
        return False

    def archive_manager_department_ids(self, request):
        """Departments whose archived records this user may see, restore and permanently delete."""
        return ()


def get_access_policy():
    path = getattr(settings, "METADATA_ACCESS_POLICY", "metadata.access.NoAccessPolicy")
    return import_string(path)()
