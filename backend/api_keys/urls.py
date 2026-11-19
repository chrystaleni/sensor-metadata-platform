from rest_framework.routers import SimpleRouter
from .views import APIKeyViewSet
router = SimpleRouter()
router.register("api-keys", APIKeyViewSet, basename="api-key")
urlpatterns = router.urls
