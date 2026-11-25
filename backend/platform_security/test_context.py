import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from metadata.tests.test_backend import create_catalog
from .models import UserRole, UserDepartment

pytestmark=pytest.mark.django_db

@pytest.mark.parametrize('role,writable,manage', [('VIEWER',False,False),('EDITOR',True,False),('DEPARTMENT_ADMIN',True,True),('SYSTEM_ADMIN',True,True)])
def test_context_is_membership_and_role_scoped(settings,role,writable,manage):
 settings.METADATA_ACCESS_POLICY='platform_security.access.DepartmentAccessPolicy'
 create_catalog()
 user=get_user_model().objects.create_user(username='context-user')
 UserRole.objects.create(user=user,role=role)
 UserDepartment.objects.create(user=user,department_id=2)
 c=Client();c.force_login(user)
 data=c.get('/api/v1/auth/context/').json()
 assert data['authenticated']
 assert {d['id'] for d in data['departments']}==({1,2,3} if role=='SYSTEM_ADMIN' else {2})
 assert all(d['writable']==writable for d in data['departments'])
 assert data['permissions']['manage_catalogs']==manage
 assert data['permissions']['manage_api_keys']==(role in ('DEPARTMENT_ADMIN','SYSTEM_ADMIN'))
 assert 'no-store' in c.get('/api/v1/auth/context/').headers['Cache-Control']

def test_context_default_denies_and_does_not_expose_other_users(settings):
 settings.METADATA_ACCESS_POLICY='metadata.access.NoAccessPolicy'
 create_catalog();user=get_user_model().objects.create_user(username='context-user')
 UserRole.objects.create(user=user,role='SYSTEM_ADMIN')
 c=Client();c.force_login(user)
 data=c.get('/api/v1/auth/context/').json()
 assert data['departments']==[]
 assert not any(data['permissions'].values())
 c.logout();assert not c.get('/api/v1/auth/context/').json()['authenticated']
