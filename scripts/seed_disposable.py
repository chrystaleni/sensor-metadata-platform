"""Run only with manage.py shell inside the disposable validation runner."""
import os
from django.conf import settings
from django.core.management import call_command
from django.contrib.auth import get_user_model
from local_departments.models import Organisation, Department
from platform_security.models import UserRole, UserDepartment
from metadata.models import MeasurementType, MeasurementUnit, PhysicalDeviceType, NetworkElementType, PhysicalDevice

if os.environ.get('SENSOR_DISPOSABLE_VALIDATION') != '1' or not settings.DATABASES['default']['NAME'].startswith('sensor_validation_'):
    raise RuntimeError('This seed is restricted to the explicitly disposable validation database.')
call_command('provision_platform_department')
platform = Department.objects.get(organisation__code='platform')
settings.METADATA_PLATFORM_DEPARTMENT_ID = platform.pk
org = Organisation.objects.create(code='e2e-north',name='E2E North Organisation')
other = Organisation.objects.create(code='e2e-south',name='E2E South Organisation')
north = Department.objects.create(name='E2E North',organisation=org)
south = Department.objects.create(name='E2E South',organisation=other)
east = Department.objects.create(name='E2E East',organisation=org)
for model, name in ((PhysicalDeviceType,'E2E Device Type'),(NetworkElementType,'E2E Element Type'),(MeasurementType,'E2E Measurement Type'),(MeasurementUnit,'E2E Unit')):
    model.objects.create(name=name,department=platform)
for username,role in (('e2e-admin','DEPARTMENT_ADMIN'),('e2e-viewer','VIEWER')):
    user=get_user_model().objects.create_user(username=username,password=os.environ['E2E_PASSWORD'])
    UserRole.objects.create(user=user,role=role)
    UserDepartment.objects.create(user=user,department=north)
    if username=='e2e-admin':UserDepartment.objects.create(user=user,department=east)
PhysicalDevice.objects.create(name='Restricted East Device',department=east,device_type=PhysicalDeviceType.objects.get(name='E2E Device Type'))
PhysicalDevice.objects.create(name='Restricted South Device',department=south,device_type=PhysicalDeviceType.objects.get(name='E2E Device Type'))
print('Disposable E2E fixtures created; no credentials are printed.')

# A valid workbook with relationships, distinct from the browser-created records.
import json
from openpyxl import Workbook
from metadata.imports import SHEETS
examples={
 'Physical Devices': {'name':'E2E Imported Device','device_type':PhysicalDeviceType.objects.get(name='E2E Device Type').pk,'ref':'import-device','location':json.dumps({'type':'Point','coordinates':[33.38,35.17]})},
 'Network Elements': {'name':'E2E Imported Element','element_type':NetworkElementType.objects.get(name='E2E Element Type').pk,'ref':'import-element','geometry':json.dumps({'type':'Point','coordinates':[33.39,35.18]})},
 'Measurements': {'name':'E2E Imported Measurement','physical_device':'@import-device','network_element':'@import-element','measurement_type':MeasurementType.objects.get(name='E2E Measurement Type').pk,'measurement_unit':MeasurementUnit.objects.get(name='E2E Unit').pk},
}
workbook=Workbook();workbook.remove(workbook.active)
for title,spec in SHEETS.items():
    sheet=workbook.create_sheet(title);headers=(*spec.required,*spec.optional);sheet.append(headers);sheet.append([examples[title].get(header) for header in headers])
workbook.save(os.environ['E2E_IMPORT_WORKBOOK']);workbook.close()
