import {describe,it,expect} from 'vitest';
import {cloneData,validateRecord} from './data';
const data=cloneData();
const measurement={externalId:'M-NEW',name:'Test measurement',type:'Flow',unit:'m³/h',device:'d1',network:'n1'};
describe('Phase 1/2 metadata validation',()=>{
 it('requires four measurement relationships/values',()=>{
  for(const key of ['type','unit','device','network'])expect(validateRecord('measurements',{...measurement,[key]:''},data)).toMatch(/required/i);
 });
 it('rejects duplicate ID and name',()=>{
  expect(validateRecord('measurements',{...measurement,externalId:'DEMO-M001'},data)).toMatch(/identifier already exists/i);
  expect(validateRecord('measurements',{...measurement,name:'Flow at Station A'},data)).toMatch(/name already exists/i);
 });
 it('rejects inactive linked records',()=>{
  expect(validateRecord('measurements',{...measurement,device:'missing'},data)).toMatch(/active Physical Device/);
 });
 it('validates WGS84 point coordinates',()=>{
  const device={externalId:'D-NEW',name:'Test device',type:'Sensor',latitude:'91',longitude:'33'};
  expect(validateRecord('physical-devices',device,data)).toMatch(/Latitude/);
  expect(validateRecord('physical-devices',{...device,latitude:'35',longitude:'181'},data)).toMatch(/Longitude/);
 });
 it('validates line and polygon GeoJSON',()=>{
  const base={externalId:'N-NEW',name:'Test element',type:'Pipe',geometryType:'LineString'};
  expect(validateRecord('network-elements',{...base,geometry:'{"type":"LineString","coordinates":[[33,35]]}'},data)).toMatch(/at least two/);
  expect(validateRecord('network-elements',{...base,geometry:'{"type":"LineString","coordinates":[[33,35],[34,36]]}'},data)).toBe('');
 });
});

describe('GIS LineString validation regression',()=>{
 const base={externalId:'N-LINE',name:'Test line',type:'Pipe',geometryType:'LineString'};
 const check=coordinates=>validateRecord('network-elements',{...base,geometry:JSON.stringify({type:'LineString',coordinates})},data);
 it('rejects duplicate consecutive or repeated-only positions',()=>{
  expect(check([[33,35],[33,35]])).toMatch(/distinct/i);
  expect(check([[33,35],[33,35],[33,35]])).toMatch(/distinct/i);
 });
 it('rejects malformed nesting and invalid positions',()=>{
  expect(check([[[33,35],[34,36]]])).toMatch(/valid (?:2D )?WGS84/i);
  expect(check([[33,35],[null,36]])).toMatch(/valid (?:2D )?WGS84/i);
  expect(check([[33,35],[181,36]])).toMatch(/valid (?:2D )?WGS84/i);
 });
 it('accepts two distinct valid positions',()=>{
  expect(check([[33,35],[34,36]])).toBe('');
 });
});
