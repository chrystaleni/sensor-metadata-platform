from django.conf import settings

from local_departments.models import Department

from .models import MeasurementType, MeasurementUnit, NetworkElementType, PhysicalDeviceType


PLATFORM_CODE = "platform"
PLATFORM_NAME = "Platform"
CONTROLLED_LISTS = (MeasurementType, MeasurementUnit, PhysicalDeviceType, NetworkElementType)


def catalogs_belong_to(department_id):
    return all(
        not model.objects.exclude(department_id=department_id).exists()
        for model in CONTROLLED_LISTS
    )


def configured_platform_department_id():
    department_id = settings.METADATA_PLATFORM_DEPARTMENT_ID
    if type(department_id) is not int or not 0 < department_id < 2**63:
        return None
    candidates = list(
        Department.objects.filter(organisation__code=PLATFORM_CODE, organisation__name=PLATFORM_NAME)
        .order_by("pk").values_list("pk", flat=True)[:2]
    )
    if candidates == [department_id] and catalogs_belong_to(department_id):
        return department_id
    return None
