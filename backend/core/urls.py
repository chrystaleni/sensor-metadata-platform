from django.urls import path

from .views import health, ready

urlpatterns = [
    path("ready/", ready, name="ready"),
    path("health/", health, name="health"),
]
