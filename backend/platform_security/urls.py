from django.urls import path

from . import views
from .context import access_context


urlpatterns = [
    path("context/", access_context, name="session-context"),
    path("csrf/", views.csrf, name="session-csrf"),
    path("login/", views.login, name="session-login"),
    path("session/", views.session, name="session-status"),
    path("logout/", views.logout, name="session-logout"),
]
