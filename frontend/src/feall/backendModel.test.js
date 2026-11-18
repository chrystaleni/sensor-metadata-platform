import {describe,it,expect} from 'vitest';
import {parseRecordForm,csvFromRows} from './backendModel';
describe('Django serializer mapping',()=>{
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
