import hashlib
import hmac
import re

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.permissions import SAFE_METHODS

from .models import APIKey
from .permissions import managed_departments


class InvalidAPIKey(APIException):
    # SessionAuthentication remains first to preserve the existing session/403 contract.
    # A key-specific failure must still be 401, even with that authentication ordering.
    status_code = 401
    default_detail = "Invalid, expired or revoked API key."
    default_code = "invalid_api_key"
    auth_header = "X-API-Key"


class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        raw = request.headers.get("X-API-Key")
        if raw is None:
            return None
        match = re.fullmatch(r"smk_([0-9a-f]{32})\.([A-Za-z0-9_-]{43})", raw)
        if not match:
            raise InvalidAPIKey()
        key = APIKey.objects.select_related("created_by", "department").filter(prefix=match[1]).first()
        if key is None or not hmac.compare_digest(key.digest, hashlib.sha256(raw.encode()).hexdigest()):
            raise InvalidAPIKey()
        if key.revoked_at is not None or key.expires_at <= timezone.now() or key.created_by is None:
            raise InvalidAPIKey()
        if not managed_departments(key.created_by).filter(pk=key.department_id).exists():
            raise InvalidAPIKey()
        if request.method not in SAFE_METHODS:
            raise PermissionDenied("API keys provide read-only access.")
        requested = request.query_params.get("department")
        if requested is not None:
            try:
                if int(requested) != key.department_id:
                    raise NotFound()
            except ValueError:
                # The normal metadata filter reports malformed values as 400.
                pass
        return key.created_by, key

    def authenticate_header(self, request):
        return "X-API-Key"


class KeyAwareSessionAuthentication(SessionAuthentication):
    """A supplied key is authoritative; a browser session cannot widen its scope."""
    def authenticate(self, request):
        if request.headers.get("X-API-Key") is not None:
            return None
        return super().authenticate(request)
