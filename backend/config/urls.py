"""URL configuration for the development project."""

from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("api/v1/auth/", include("platform_security.urls")),
    path("api/v1/", include("metadata.urls")),
]
