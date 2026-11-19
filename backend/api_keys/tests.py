from datetime import timedelta
import hashlib

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from local_departments.models import Department
from metadata.models import PhysicalDevice
from metadata.tests.test_backend import create_catalog
from platform_security.models import UserRole,UserDepartment
from .models import APIKey

pytestmark=pytest.mark.django_db

@pytest.fixture
def fixture(settings):
 settings.METADATA_ACCESS_POLICY='platform_security.access.DepartmentAccessPolicy'
 settings.METADATA_PLATFORM_DEPARTMENT_ID=1
 catalog=create_catalog()
 admin=get_user_model().objects.create_user(username='key-owner',password='test-only-password')
 UserRole.objects.create(user=admin,role='DEPARTMENT_ADMIN')
 UserDepartment.objects.create(user=admin,department_id=2)
 north=PhysicalDevice.objects.create(name='North',department_id=2,device_type_id=catalog['device_type'])
 south=PhysicalDevice.objects.create(name='South',department_id=3,device_type_id=catalog['device_type'])
 key,raw=APIKey.issue(name='Integration',department=Department.objects.get(pk=2),creator=admin,expires_at=timezone.now()+timedelta(days=1))
 return admin,north,south,key,raw

def key_client(raw):
 c=APIClient();c.credentials(HTTP_X_API_KEY=raw);return c

def test_hash_storage_and_one_time_display(fixture):
 admin,_,_,key,raw=fixture
 assert key.digest==hashlib.sha256(raw.encode()).hexdigest()
 assert raw not in str(APIKey.objects.values().get(pk=key.pk))
 c=APIClient();c.force_authenticate(admin)
 response=c.post('/api/v1/api-keys/',{'name':'New','department':2},format='json')
 assert response.status_code==201,response.data
 assert response.data['key'].startswith('smk_')
 assert 'digest' not in response.data
 assert 'no-store' in response.headers['Cache-Control']
 response=c.get('/api/v1/api-keys/')
 assert response.status_code==200
 assert all('key' not in row and 'digest' not in row for row in response.data['results'])

def test_readonly_scope_and_shared_catalog_reads(fixture):
 _,north,south,_,raw=fixture;c=key_client(raw)
 response=c.get('/api/v1/physical-devices/')
 assert response.status_code==200,response.data
 assert {r['id'] for r in response.data['results']}=={north.pk}
 assert c.get(f'/api/v1/physical-devices/{south.pk}/').status_code==404
 assert c.get('/api/v1/physical-devices/?department=3').status_code==404
 assert c.get('/api/v1/physical-device-types/').status_code==200
 for method in ('post','patch','delete'):
  path='/api/v1/physical-devices/' if method=='post' else f'/api/v1/physical-devices/{north.pk}/'
  assert getattr(c,method)(path,{},format='json').status_code==403
 assert c.post('/api/v1/imports/excel/',{}).status_code==403
 assert c.get('/api/v1/api-keys/').status_code==403
 north.refresh_from_db();assert north.deleted_at is None

@pytest.mark.parametrize('state',['invalid','malformed','expired','revoked','inactive-owner','lost-role','lost-membership','default-deny'])
def test_invalid_keys_fail_closed(fixture,settings,state):
 admin,_,_,key,raw=fixture
 if state=='invalid':raw=raw[:-1]+('a' if raw[-1]!='a' else 'b')
 elif state=='malformed':raw='invalid'
 elif state=='expired':APIKey.objects.filter(pk=key.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
 elif state=='revoked':APIKey.objects.filter(pk=key.pk).update(revoked_at=timezone.now())
 elif state=='inactive-owner':admin.is_active=False;admin.save()
 elif state=='lost-role':UserRole.objects.filter(user=admin).delete()
 elif state=='lost-membership':UserDepartment.objects.filter(user=admin).delete()
 elif state=='default-deny':settings.METADATA_ACCESS_POLICY='metadata.access.NoAccessPolicy'
 response=key_client(raw).get('/api/v1/measurements/')
 assert response.status_code==401,response.data
 assert raw not in str(response.data)

def test_admins_cannot_manage_or_create_cross_department_keys(fixture):
 admin,_,_,key,_=fixture;c=APIClient();c.force_authenticate(admin)
 assert c.post('/api/v1/api-keys/',{'name':'Wrong','department':3},format='json').status_code==404
 assert c.get('/api/v1/api-keys/?department=3').status_code==404
 other=get_user_model().objects.create_user(username='system')
 UserRole.objects.create(user=other,role='SYSTEM_ADMIN')
 foreign,_=APIKey.issue(name='Other',department=Department.objects.get(pk=3),creator=other,expires_at=timezone.now()+timedelta(days=1))
 assert c.delete(f'/api/v1/api-keys/{foreign.pk}/').status_code==404
 assert c.delete(f'/api/v1/api-keys/{key.pk}/').status_code==204
 key.refresh_from_db();assert key.revoked_at is not None

@pytest.mark.parametrize('role',['VIEWER','EDITOR',None])
def test_non_administrators_cannot_manage_keys(fixture,role):
 admin,_,_,_,_=fixture
 if role:UserRole.objects.filter(user=admin).update(role=role)
 else:UserRole.objects.filter(user=admin).delete()
 c=APIClient();c.force_authenticate(admin)
 assert c.get('/api/v1/api-keys/').status_code==403
 assert c.post('/api/v1/api-keys/',{'name':'Blocked','department':2},format='json').status_code==403

def test_key_header_cannot_borrow_a_more_privileged_session(fixture):
 admin,_,south,_,raw=fixture
 UserRole.objects.filter(user=admin).update(role='SYSTEM_ADMIN')
 c=key_client(raw);c.force_login(admin)
 assert c.get(f'/api/v1/physical-devices/{south.pk}/').status_code==404
 assert c.post('/api/v1/physical-devices/',{},format='json').status_code==403
 assert c.get('/api/v1/api-keys/').status_code==403


def test_management_requires_real_session_csrf(fixture):
 admin,*_=fixture
 c=APIClient(enforce_csrf_checks=True);c.force_login(admin)
 payload={'name':'CSRF protected','department':2}
 assert c.post('/api/v1/api-keys/',payload,format='json').status_code==403
 c.get('/api/v1/auth/csrf/')
 response=c.post('/api/v1/api-keys/',payload,format='json',HTTP_X_CSRFTOKEN=c.cookies['csrftoken'].value)
 assert response.status_code==201,response.data


def test_expired_creation_request_does_not_store_a_key(fixture):
 admin,*_=fixture;c=APIClient();c.force_authenticate(admin)
 count=APIKey.objects.count()
 response=c.post('/api/v1/api-keys/',{'name':'Expired','department':2,'expires_at':(timezone.now()-timedelta(days=1)).isoformat()},format='json')
 assert response.status_code==400
 assert APIKey.objects.count()==count
