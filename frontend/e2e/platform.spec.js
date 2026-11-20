
import {test,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';

async function login(page,username='e2e-admin'){
 await page.goto('/');await page.getByLabel('Username',{exact:true}).fill(username);
 await page.getByLabel('Password',{exact:true}).fill(process.env.E2E_PASSWORD);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByLabel('Department',{exact:true})).toContainText('E2E North');
}

async function choose(dialog,label,text){
 const select=dialog.getByRole('combobox',{name:label,exact:true});
 await expect(select).toBeVisible();
 await expect.poll(async()=>{
  return select.evaluate((element,expected)=>
   Array.from(element.options).some(option=>option.textContent.includes(expected)),text);
 }).toBe(true);
 const value=await select.evaluate((element,expected)=>
  Array.from(element.options).find(option=>option.textContent.includes(expected))?.value,text);
 await select.selectOption(value);
}

async function create(page,section,name,fields){
 await page.getByRole('link',{name:section,exact:true}).click();
 await page.getByRole('button',{name:/^\+ Add(?: .+)?$/}).click();
 const dialog=page.getByRole('dialog');
 await dialog.getByLabel('Name *',{exact:true}).fill(name);
 await fields(dialog);
 const response=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().includes('/api/v1/'));
 await dialog.getByRole('button',{name:'Save to Django'}).click();
 expect((await response).status()).toBe(201);
 await expect(dialog).not.toBeVisible();
 await expect(page.getByRole('cell',{name,exact:true})).toBeVisible();
}

async function verifyDescription(page,row,description){
 await row.getByRole('button',{name:'View',exact:true}).click();
 const details=page.getByRole('dialog');
 await expect(details.getByText(description,{exact:true})).toBeVisible();
 await details.getByRole('button',{name:'Close details',exact:true}).click();
 await expect(details).not.toBeVisible();
}

test('real session, relational CRUD, persistence, GIS, export and scoped API keys',async({page})=>{
 await login(page);

 await create(page,'Physical Devices','E2E Device',async dialog=>{
  await choose(dialog,'Device Type *','E2E Device Type');
  await dialog.getByLabel('Location (GeoJSON Point)',{exact:true}).fill('{"type":"Point","coordinates":[33.36,35.15]}');
 });

 const deviceRow=page.getByRole('row').filter({has:page.getByRole('cell',{name:'E2E Device',exact:true})});
 await deviceRow.getByRole('button',{name:'Edit',exact:true}).click();
 await page.getByRole('dialog').getByLabel('Description',{exact:true}).fill('Updated via browser');
 await page.getByRole('button',{name:'Save to Django'}).click();

 await verifyDescription(page,deviceRow,'Updated via browser');
 await page.reload();
 await verifyDescription(page,deviceRow,'Updated via browser');

 const department=page.getByLabel('Department',{exact:true});
 const north=await department.inputValue();
 const east=await department.locator('option').filter({hasText:'E2E East'}).getAttribute('value');

 await department.selectOption(east);
 await expect(page.getByRole('cell',{name:'Restricted East Device',exact:true})).toBeVisible();
 await expect(page.getByRole('cell',{name:'E2E Device',exact:true})).not.toBeVisible();

 await department.selectOption(north);
 await expect(page.getByRole('cell',{name:'E2E Device',exact:true})).toBeVisible();

 await page.getByLabel('Search records').fill('missing-e2e-record');
 await expect(page.getByText(/No matching records/)).toBeVisible();

 await page.getByLabel('Search records').fill('E2E');
 await expect(page.getByRole('cell',{name:'E2E Device',exact:true})).toBeVisible();

 await create(page,'Network Elements','E2E Element',async dialog=>{
  await choose(dialog,'Element Type *','E2E Element Type');
  await dialog.getByLabel('Geometry (GeoJSON)',{exact:true}).fill('{"type":"LineString","coordinates":[[33.36,35.15],[33.37,35.16]]}');
  await dialog.getByLabel('External Identifiers (JSON array; blank preserves, [] clears)',{exact:true}).fill('[{"source":"e2e","value":"node-1"}]');
 });

 const elementRow=page.getByRole('row').filter({has:page.getByRole('cell',{name:'E2E Element',exact:true})});
 await elementRow.getByRole('button',{name:'Edit',exact:true}).click();
 await page.getByRole('dialog').getByLabel('Description',{exact:true}).fill('Updated network element');
 await page.getByRole('dialog').getByRole('textbox',{name:'Geometry (GeoJSON)',exact:true}).fill('{"type":"Polygon","coordinates":[[[33,35],[34,35],[34,36],[33,35]]]}');
 await page.getByRole('button',{name:'Save to Django'}).click();
 await verifyDescription(page,elementRow,'Updated network element');

 await create(page,'Measurements','E2E Measurement',async dialog=>{
  await choose(dialog,'Physical Device *','E2E Device');
  await choose(dialog,'Network Element *','E2E Element');
  await choose(dialog,'Measurement Type *','E2E Measurement Type');
  await choose(dialog,'Measurement Unit *','E2E Unit');
  await dialog.getByLabel('Collection Config (JSON)',{exact:true}).fill('{"protocol":"https","extra_settings":{"poll_seconds":60}}');
 });

 let row=page.getByRole('row').filter({has:page.getByRole('cell',{name:'E2E Measurement',exact:true})});
 await row.getByRole('button',{name:'Edit',exact:true}).click();
 await page.getByRole('dialog').getByLabel('Name *',{exact:true}).fill('E2E Updated Measurement');
 await page.getByRole('button',{name:'Save to Django'}).click();
 await expect(page.getByRole('cell',{name:'E2E Updated Measurement',exact:true})).toBeVisible();

 const measurementId=await page.getByRole('row').filter({has:page.getByRole('cell',{name:'E2E Updated Measurement',exact:true})}).getByRole('cell').first().textContent();

 await page.getByRole('link',{name:'GIS Map',exact:true}).click();
 await expect(page.getByLabel('Interactive geographic map')).toHaveClass(/leaflet-container/);
 await expect(page.getByRole('button',{name:/E2E Device.*Physical Device/})).toBeVisible();
 await expect(page.getByRole('button',{name:/E2E Element.*Network Element/})).toBeVisible();

 await page.getByRole('link',{name:'Excel Import/Export',exact:true}).click();
 await page.getByLabel(/Select Excel workbook/).setInputFiles(process.env.E2E_IMPORT_WORKBOOK);

 const imported=page.waitForResponse(r=>r.url().endsWith('/imports/excel/')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Import workbook',exact:true}).click();
 expect((await imported).status()).toBe(201);
 await expect(page.getByText(/Workbook imported successfully/)).toBeVisible();

 await page.getByRole('link',{name:'GIS Map',exact:true}).click();
 await expect(page.getByRole('button',{name:/E2E Imported Device.*Physical Device/})).toBeVisible();

 await page.getByRole('link',{name:'Dashboard',exact:true}).click();
 for(const stat of await page.locator('.fe-stat strong').all()){
  await expect(stat).toHaveText('2');
 }

 await page.getByRole('link',{name:'Excel Import/Export',exact:true}).click();
 const download=page.waitForEvent('download');
 await page.getByRole('button',{name:'Download XLSX'}).click();

 const exported=await download;
 expect(exported.suggestedFilename()).toBe('measurements.xlsx');

 execFileSync(process.env.E2E_PYTHON,[
  '-c',
  "import sys; from openpyxl import load_workbook; w=load_workbook(open(sys.argv[1],'rb'),read_only=True); assert any('E2E Updated Measurement' in row for row in w.active.iter_rows(values_only=True)); w.close()",
  await exported.path()
 ],{stdio:'pipe'});

 await page.getByLabel('Export format').selectOption('csv');
 const csvDownload=page.waitForEvent('download');
 await page.getByRole('button',{name:'Download CSV'}).click();
 expect((await csvDownload).suggestedFilename()).toBe('measurements.csv');

 await page.getByRole('link',{name:'API Keys',exact:true}).click();
 await page.getByLabel('Key name').fill('E2E SCADA');
 await page.getByRole('button',{name:'Create API key',exact:true}).click();

 const key=await page.locator('code').filter({hasText:/^smk_/}).textContent();
 const response=await page.request.get('/api/v1/physical-devices/',{headers:{'X-API-Key':key}});
 expect(response.status()).toBe(200);

 const data=JSON.stringify(await response.json());
 expect(data).not.toContain('Restricted South');
 expect(data).not.toContain('Restricted East');

 expect((await page.request.get(`/api/v1/physical-devices/${process.env.E2E_EAST_DEVICE_ID}/`)).status()).toBe(200);
 expect((await page.request.get(`/api/v1/physical-devices/${process.env.E2E_EAST_DEVICE_ID}/`,{headers:{'X-API-Key':key}})).status()).toBe(404);

 const configuration=await page.request.get(`/api/v1/measurements/${measurementId}/`,{headers:{'X-API-Key':key}});
 expect(configuration.status()).toBe(200);
 expect((await configuration.json()).data_collection_config).toEqual({
  protocol:'https',
  extra_settings:{poll_seconds:60}
 });

 expect((await page.request.post('/api/v1/physical-devices/',{headers:{'X-API-Key':key},data:{}})).status()).toBe(403);

 await page.getByRole('button',{name:'Revoke E2E SCADA'}).click();
 await expect(page.getByRole('button',{name:'Revoke E2E SCADA'})).not.toBeVisible();
 expect((await page.request.get('/api/v1/physical-devices/',{headers:{'X-API-Key':key}})).status()).toBe(401);

 for(const [section,name] of [
  ['Measurements','E2E Updated Measurement'],
  ['Physical Devices','E2E Device'],
  ['Network Elements','E2E Element']
 ]){
  await page.getByRole('link',{name:section,exact:true}).click();
  row=page.getByRole('row').filter({has:page.getByRole('cell',{name,exact:true})});
  page.once('dialog',dialog=>dialog.accept());
  await row.getByRole('button',{name:'Archive',exact:true}).click();
  await expect(page.getByRole('cell',{name,exact:true})).not.toBeVisible();
 }

 await page.getByRole('button',{name:'Log out',exact:true}).click();
 await expect(page.getByLabel('Password',{exact:true})).toBeVisible();
});

test('viewer controls and cross-Organisation isolation are enforced by Django',async({page})=>{
 await login(page,'e2e-viewer');

 await expect(page.getByLabel('Department',{exact:true})).not.toContainText('E2E East');
 await page.getByRole('link',{name:'Physical Devices',exact:true}).click();
 await expect(page.getByRole('button',{name:/^\+ Add(?: .+)?$/})).not.toBeVisible();

 const response=await page.request.get('/api/v1/physical-devices/');
 expect(response.status()).toBe(200);
 expect(JSON.stringify(await response.json())).not.toContain('Restricted South Device');

 expect((await page.request.get(`/api/v1/physical-devices/${process.env.E2E_SOUTH_DEVICE_ID}/`)).status()).toBe(404);

 const csrf=(await page.context().cookies()).find(c=>c.name==='csrftoken').value;
 const types=await (await page.request.get('/api/v1/physical-device-types/')).json();

 const denied=await page.request.post('/api/v1/physical-devices/',{
  headers:{'X-CSRFToken':csrf},
  data:{
   name:'Denied',
   department:Number(await page.getByLabel('Department',{exact:true}).inputValue()),
   device_type:types.results[0].id
  }
 });

 expect(denied.status()).toBe(403);
 expect(JSON.stringify(await denied.json())).not.toContain('CSRF');

 await page.getByRole('button',{name:'Log out',exact:true}).click();
});

test('expired server-side sessions return to login after refresh',async({page})=>{
 await login(page);

 const cookie=(await page.context().cookies()).find(c=>c.name==='sessionid');

 if(
  process.env.SENSOR_DISPOSABLE_VALIDATION!=='1' ||
  !process.env.POSTGRES_DB?.startsWith('sensor_validation_')
 ){
  throw Error('Disposable runner required.');
 }

 execFileSync(process.env.E2E_PYTHON,[
  'manage.py',
  'shell',
  '-c',
  "import os; from datetime import timedelta; from django.utils import timezone; from django.contrib.sessions.models import Session; Session.objects.filter(session_key=os.environ['E2E_SESSION']).update(expire_date=timezone.now()-timedelta(seconds=1))"
 ],{
  cwd:process.env.E2E_BACKEND_DIR,
  env:{...process.env,E2E_SESSION:cookie.value},
  stdio:'pipe'
 });

 await page.reload();
 await expect(page.getByLabel('Password',{exact:true})).toBeVisible();
});
