"""URL configuration for the development project."""

from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
]
