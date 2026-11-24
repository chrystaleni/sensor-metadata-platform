"""URL configuration for the development project."""

from django.urls import include, path

from core.docs import docs, schema_view

urlpatterns = [
    path("", include("core.urls")),
    path("api/v1/openapi.json", schema_view, name="openapi-schema"),
    path("api/v1/docs/", docs, name="api-docs"),
    path("api/v1/auth/", include("platform_security.urls")),
    path("api/v1/", include("platform_security.admin_urls")),
    path("api/v1/", include("metadata.urls")),
    path("api/v1/", include("api_keys.urls")),
]
