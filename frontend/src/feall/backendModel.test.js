import {describe,it,expect} from 'vitest';
import {parseRecordForm,csvFromRows} from './backendModel';
describe('Django serializer mapping',()=>{
 it.each([undefined, '', '   '])('omits blank external identifiers on create (%s)', external_identifiers => {
  const dto=parseRecordForm('network-elements',{name:'Site',element_type:'1',external_identifiers},'2');
  expect(dto).not.toHaveProperty('external_identifiers');
  expect(dto).toMatchObject({department:2,element_type:1});
 });
 it('preserves existing identifiers by omitting a blank PATCH field',()=>{
  const dto=parseRecordForm('network-elements',{name:'Site',element_type:'1',external_identifiers:''},'2',true);
  expect(dto).not.toHaveProperty('external_identifiers');
  expect(dto).not.toHaveProperty('department');
 });
 it('keeps an explicit empty array so identifiers can be cleared',()=>{
  const dto=parseRecordForm('network-elements',{name:'Site',element_type:'1',external_identifiers:'[]'},'2',true);
  expect(dto.external_identifiers).toEqual([]);
 });
 it('preserves explicit identifier pairs',()=>{
  const pairs=[{source:'ERP',value:'site-42'}];
  const dto=parseRecordForm('network-elements',{name:'Site',element_type:'1',external_identifiers:JSON.stringify(pairs)},'2',true);
  expect(dto.external_identifiers).toEqual(pairs);
 });
 it('rejects an explicit null identifier list',()=>{
  expect(()=>parseRecordForm('network-elements',{name:'Site',element_type:'1',external_identifiers:'null'},'2')).toThrow(/array/);
 });

 it('sends numeric relationships and department on create',()=>{
  const dto=parseRecordForm('measurements',{name:'Flow',physical_device:'4',network_element:'5',measurement_type:'6',measurement_unit:'7'},'2');
  expect(dto).toMatchObject({name:'Flow',department:2,physical_device:4,network_element:5,measurement_type:6,measurement_unit:7});
 });
 it('does not reassign department on update',()=>{
  const dto=parseRecordForm('physical-devices',{name:'Device',device_type:'3'},'2',true);
  expect(dto).not.toHaveProperty('department');
 });
 it('rejects invalid JSON',()=>expect(()=>parseRecordForm('network-elements',{name:'A',element_type:1,geometry:'bad'},2)).toThrow(/valid JSON/));
 it('escapes CSV formulas as plain quoted data',()=>expect(csvFromRows([{name:'A,"B"'}],['name'])).toContain('"A,""B"""'));
});

describe('CSV formula protection',()=>{
 it.each(['=1+1','+SUM(1,2)','-1+2','@SUM(1,2)','  =1+1','\t=1+1','\r=1+1','\n=1+1'])('neutralizes spreadsheet formulas %j',name=>{
  expect(csvFromRows([{name}],['name']).split('\r\n')[1]).toBe(`"'${name}"`);
 });
 it('retains literal text, quotes and unicode',()=>{
  expect(csvFromRows([{name:'Σταθμός "A"'}],['name'])).toContain('"Σταθμός ""A"""');
 });
});
