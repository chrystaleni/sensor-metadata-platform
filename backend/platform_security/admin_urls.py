from rest_framework.routers import SimpleRouter

from .admin_api import DepartmentViewSet, OrganisationViewSet, UserViewSet

router = SimpleRouter()
router.register("users", UserViewSet, basename="user")
router.register("organisations", OrganisationViewSet, basename="organisation")
router.register("departments", DepartmentViewSet, basename="department")

urlpatterns = router.urls
