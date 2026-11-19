"""Database-free boundary tests. These do not replace the PostGIS integration tests."""
import hashlib
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from .authentication import APIKeyAuthentication, InvalidAPIKey, KeyAwareSessionAuthentication
from .models import APIKey

RAW = 'smk_' + 'a' * 32 + '.' + 'b' * 43

@pytest.fixture
def boundary(monkeypatch):
    user = get_user_model()(id=5, username='unit', is_active=True)
    key = APIKey(id=1, prefix='a'*32, digest=hashlib.sha256(RAW.encode()).hexdigest(),
                 department_id=7, created_by=user, expires_at=timezone.now()+timedelta(days=1))
    query = Mock();query.filter.return_value.first.return_value = key
    monkeypatch.setattr(APIKey.objects, 'select_related', lambda *args: query)
    scope = Mock();scope.filter.return_value.exists.return_value = True
    monkeypatch.setattr('api_keys.authentication.managed_departments', lambda user: scope)
    request = SimpleNamespace(headers={'X-API-Key': RAW}, method='GET', query_params={})
    return key, request, scope


def test_valid_key_uses_issuer_and_key_principal(boundary):
    key, request, _ = boundary
    assert APIKeyAuthentication().authenticate(request) == (key.created_by, key)


@pytest.mark.parametrize('method', ['POST','PUT','PATCH','DELETE'])
def test_key_writes_rejected_before_view_execution(boundary, method):
    _, request, _ = boundary;request.method=method
    with pytest.raises(PermissionDenied):APIKeyAuthentication().authenticate(request)


@pytest.mark.parametrize('state', ['bad-hash','expired','revoked','lost-scope','missing-issuer'])
def test_key_failures_are_generic_401(boundary,state):
    key, request, scope = boundary
    if state=='bad-hash':key.digest='0'*64
    elif state=='expired':key.expires_at=timezone.now()-timedelta(seconds=1)
    elif state=='revoked':key.revoked_at=timezone.now()
    elif state=='missing-issuer':key.created_by=None
    else:scope.filter.return_value.exists.return_value=False
    with pytest.raises(InvalidAPIKey) as error:APIKeyAuthentication().authenticate(request)
    assert error.value.status_code==401
    assert RAW not in str(error.value)


def test_cross_department_filter_is_hidden(boundary):
    _, request, _ = boundary;request.query_params={'department':'8'}
    with pytest.raises(NotFound):APIKeyAuthentication().authenticate(request)


def test_malformed_key_is_401():
    with pytest.raises(InvalidAPIKey):
        APIKeyAuthentication().authenticate(SimpleNamespace(headers={'X-API-Key':'invalid'}))


def test_key_header_disables_session_authentication():
    assert KeyAwareSessionAuthentication().authenticate(SimpleNamespace(headers={'X-API-Key':RAW})) is None


@pytest.mark.parametrize('department',[0,-1,2**63,'invalid',[]])
def test_management_serializer_rejects_invalid_ids_without_queries(department):
    from .views import APIKeySerializer
    serializer=APIKeySerializer(data={'name':'Test','department':department})
    assert not serializer.is_valid()
    assert 'department' in serializer.errors


def test_management_serializer_requires_a_future_expiration():
    from .views import APIKeySerializer
    serializer=APIKeySerializer(data={'name':'Test','department':7,'expires_at':(timezone.now()-timedelta(days=1)).isoformat()})
    assert not serializer.is_valid()
    assert 'expires_at' in serializer.errors
