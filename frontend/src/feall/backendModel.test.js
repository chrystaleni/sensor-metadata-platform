import {describe,it,expect} from 'vitest';
import {parseRecordForm,csvFromRows,geographicRecords} from './backendModel';
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


it('rejects coordinates that the map cannot render before submitting',()=>{
 expect(()=>parseRecordForm('physical-devices',{name:'Sensor',device_type:'1',location:JSON.stringify({type:'Point',coordinates:[200,35]})},2)).toThrow('WGS84');
});


it('maps actual Django GeoJSON and identifiers without changing record identities',()=>{
 const records=geographicRecords({'physical-devices':[{id:1,device_type:2,location:{type:'Point',coordinates:[33,35]},is_active:true}], 'physical-device-types':[{id:2,name:'Meter'}], 'network-elements':[{id:1,geometry:{type:'LineString',coordinates:[[33,35],[34,36]]},external_identifiers:[{source:'ERP',value:'node'}]}]});
 expect(records['physical-devices'][0]).toMatchObject({id:1,latitude:35,longitude:33,type:'Meter'});
 expect(records['network-elements'][0]).toMatchObject({id:1,geometryType:'LineString',externalId:'ERP: node'});
});

describe('client metadata fields',()=>{
  const element={name:'Inlet',element_type:'1'};
  it('sends network area, elevation and address for a network element',()=>{
    const dto=parseRecordForm('network-elements',{...element,network_area:'Zone 1',elevation:'120,5',address:'1 Main St'},'2');
    expect(dto).toMatchObject({network_area:'Zone 1',elevation:120.5,address:'1 Main St'});
  });
  it('sends a blank elevation as null so it can be cleared',()=>{
    expect(parseRecordForm('network-elements',{...element,elevation:''},'2',true).elevation).toBeNull();
  });
  it('rejects an elevation that is not a number or is out of range',()=>{
    expect(()=>parseRecordForm('network-elements',{...element,elevation:'high'},'2')).toThrow(/number/);
    expect(()=>parseRecordForm('network-elements',{...element,elevation:'99999'},'2')).toThrow(/between/);
  });
  it('sends communication parameters as a JSON object',()=>{
    const dto=parseRecordForm('physical-devices',{name:'Logger',device_type:'1',communication_parameters:'{"ip":"10.0.0.1","port":502}'},'2');
    expect(dto.communication_parameters).toEqual({ip:'10.0.0.1',port:502});
  });
  it('clears communication parameters when blank and rejects non-objects',()=>{
    expect(parseRecordForm('physical-devices',{name:'Logger',device_type:'1',communication_parameters:''},'2',true).communication_parameters).toBeNull();
    expect(()=>parseRecordForm('physical-devices',{name:'Logger',device_type:'1',communication_parameters:'[1]'},'2')).toThrow(/object/);
    expect(()=>parseRecordForm('physical-devices',{name:'Logger',device_type:'1',communication_parameters:'{bad'},'2')).toThrow(/JSON/);
  });
});
