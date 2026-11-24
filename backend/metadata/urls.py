from django.urls import path
from rest_framework.routers import SimpleRouter

from .imports import MetadataImportView
from .views import (
    MeasurementTypeViewSet,
    MeasurementUnitViewSet,
    MeasurementViewSet,
    NetworkElementTypeViewSet,
    NetworkElementViewSet,
    PhysicalDeviceTypeViewSet,
    PhysicalDeviceViewSet,
)


class DeviceAliasViewSet(PhysicalDeviceViewSet):
    schema = None  # same operations as /physical-devices/; keep the OpenAPI schema unambiguous


router = SimpleRouter()
router.register("measurements", MeasurementViewSet, basename="measurement")
router.register("physical-devices", PhysicalDeviceViewSet, basename="physical-device")
# Phase 2 design (Table 4) names this resource /devices; both paths are served.
router.register("devices", DeviceAliasViewSet, basename="device")
router.register("network-elements", NetworkElementViewSet, basename="network-element")
router.register("measurement-types", MeasurementTypeViewSet, basename="measurement-type")
router.register("measurement-units", MeasurementUnitViewSet, basename="measurement-unit")
router.register("physical-device-types", PhysicalDeviceTypeViewSet, basename="physical-device-type")
router.register("network-element-types", NetworkElementTypeViewSet, basename="network-element-type")

urlpatterns = [
    *router.urls,
    path("imports/excel/", MetadataImportView.as_view(), name="metadata-excel-import"),
]
