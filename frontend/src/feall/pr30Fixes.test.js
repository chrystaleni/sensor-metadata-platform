import {describe,it,expect} from 'vitest';
import {geometryError} from './geometryValidation';
import {csrfToken,createImportRequest,importSucceeded} from './excelImport';
import {groupedImportErrors} from './excelErrors';
describe('PR30 GIS security and validation',()=>{
 it('rejects 3D coordinates',()=>{
  expect(geometryError({type:'Point',coordinates:[33,35,100]})).toMatch(/2D/);
  expect(geometryError({type:'LineString',coordinates:[[33,35],[34,36,1]]})).toMatch(/2D/);
  expect(geometryError({type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,0,5]]]})).toMatch(/2D/);
 });
 it('rejects unsupported CRS',()=>expect(geometryError({type:'Point',coordinates:[33,35],crs:{type:'name',properties:{name:'EPSG:3857'}}})).toMatch(/CRS/));
 it('rejects self-intersecting polygons',()=>expect(geometryError({type:'Polygon',coordinates:[[[0,0],[2,2],[0,2],[2,0],[0,0]]]})).toMatch(/Self-intersecting/));
 it('accepts a valid simple polygon',()=>expect(geometryError({type:'Polygon',coordinates:[[[0,0],[2,0],[2,2],[0,2],[0,0]]]})).toBe(''));
});
describe('PR30 Excel upload contracts',()=>{
 it('includes workbook and department ID in multipart request with CSRF header',()=>{
  const file=new File(['x'],'data.xlsx');
  const request=createImportRequest(file,7,'token');
  expect(request.body.get('file')).toBe(file);
  expect(request.body.get('department')).toBe('7');
  expect(request.body.has('department_id')).toBe(false);
  expect(request.headers['X-CSRFToken']).toBe('token');
  expect(request.credentials).toBe('include');
 });
 it('reads CSRF cookie',()=>expect(csrfToken('a=b; csrftoken=abc%20123')).toBe('abc 123'));
 it('never treats ambiguous responses as success',()=>{
  expect(importSucceeded({ok:true},{message:'OK'})).toBe(false);
  expect(importSucceeded({ok:false},{success:true})).toBe(false);
  expect(importSucceeded({ok:true},{success:true,errors:[{sheet:'A',row:2,field:'id',message:'Invalid'}]})).toBe(false);
  expect(importSucceeded({ok:true,status:201},{created:{Measurements:1}})).toBe(true);
  expect(importSucceeded({ok:true,status:200},{success:true})).toBe(false);
 });
 it('groups Excel errors by sheet, row and field',()=>expect(groupedImportErrors({errors_by_sheet:{Devices:{4:{name:['Required']}}}})).toEqual([{sheet:'Devices',row:'4',field:'name',message:'Required'}]));
});
