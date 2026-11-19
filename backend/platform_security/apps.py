from django.apps import AppConfig
from django.contrib.auth.signals import user_logged_in


class PlatformSecurityConfig(AppConfig):
    name = "platform_security"

    def ready(self):
        from .session_expiry import start_session_lifetime

        user_logged_in.connect(start_session_lifetime, dispatch_uid="platform_security.session_lifetime")
