import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

class APIKey(models.Model):
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=32, unique=True, editable=False)
    digest = models.CharField(max_length=64, editable=False)
    department = models.ForeignKey("local_departments.Department", on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    # Optional (Phase 2, 1.4.4): no expiration means the key is valid until it is revoked.
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, *, name, department, creator, expires_at):
        if expires_at is not None and expires_at <= timezone.now():
            raise ValueError("Expiration must be in the future.")
        prefix = secrets.token_hex(16)
        raw = f"smk_{prefix}.{secrets.token_urlsafe(32)}"
        record = cls.objects.create(name=name, prefix=prefix,
            digest=hashlib.sha256(raw.encode()).hexdigest(), department=department,
            created_by=creator, expires_at=expires_at)
        return record, raw

    def is_expired(self, now=None):
        return self.expires_at is not None and self.expires_at <= (now or timezone.now())
