import {geometryError} from './geometryValidation';
export const resources = {
  measurements: {label:'Measurements', fields:[['name','Name','text',true],['description','Description','textarea'],['physical_device','Physical Device','physical-devices',true],['network_element','Network Element','network-elements',true],['measurement_type','Measurement Type','measurement-types',true],['measurement_unit','Measurement Unit','measurement-units',true],['customer_account','Customer Account'],['meter_account','Meter Account'],['data_collection_config','Collection Config (JSON)','json']]},
  'physical-devices': {label:'Physical Devices',fields:[['name','Name','text',true],['description','Description','textarea'],['device_type','Device Type','physical-device-types',true],['location','Location (GeoJSON Point)','geo'],['communication_parameters','Communication Parameters (JSON object, e.g. IP)','json']]},
  'network-elements': {label:'Network Elements',fields:[['name','Name','text',true],['description','Description','textarea'],['element_type','Element Type','network-element-types',true],['geometry','Geometry (GeoJSON)','geo'],['external_identifiers','External Identifiers (JSON array; blank preserves, [] clears)','json'],['dma_model_id','DMA Model ID'],['strategic_model_id','Strategic Model ID'],['network_area','Network Area'],['elevation','Elevation (m)','number'],['address','Address']]},
  'measurement-types':{label:'Measurement Types',fields:[['name','Name','text',true],['description','Description','textarea']]},
  'measurement-units':{label:'Measurement Units',fields:[['name','Name','text',true],['description','Description','textarea'],['symbol','Symbol']]},
  'physical-device-types':{label:'Physical Device Types',fields:[['name','Name','text',true],['description','Description','textarea']]},
  'network-element-types':{label:'Network Element Types',fields:[['name','Name','text',true],['description','Description','textarea']]},
};
export const catalogKeys=Object.keys(resources).slice(3);
export const domainKeys=Object.keys(resources).slice(0,3);
export function parseRecordForm(resource, form, department, editing=false){
  const spec=resources[resource]; if(!spec)throw Error('Unknown resource');
  const result={};
  for(const [key,,type,required] of spec.fields){
    const raw=String(form[key]??'').trim();
    if(required&&!raw)throw Error(`${key} is required.`);
    // Omit a blank identifier field on create and PATCH; [] explicitly clears it.
    if(!raw&&key==='external_identifiers')continue;
    if(!raw){if(type==='geo'||type==='json'||type==='number')result[key]=null;else if(type&&resources[type]){if(required)throw Error(`${key} is required.`);}else result[key]='';continue;}
    if(type&&resources[type]){if(!/^\d+$/.test(raw)||Number(raw)<1)throw Error(`Choose a valid ${key}.`);result[key]=Number(raw);}
    else if(type==='json'||type==='geo'){
      try{result[key]=JSON.parse(raw);}catch{throw Error(`${key} must contain valid JSON.`);}
      if(type==='geo'){
        const g=result[key];if(!g||!['Point','LineString','Polygon'].includes(g.type)||resource==='physical-devices'&&g.type!=='Point')throw Error('Unsupported geometry.');
        const error=geometryError(g);if(error)throw Error(error);
      }
      if(key==='external_identifiers'&&!Array.isArray(result[key]))throw Error('External identifiers must be an array.');
      if(key==='communication_parameters'&&(typeof result[key]!=='object'||Array.isArray(result[key])))throw Error('Communication parameters must be a JSON object.');
    }else if(type==='number'){
      const number=Number(raw.replace(',','.'));
      if(!Number.isFinite(number))throw Error(`${key} must be a number.`);
      if(key==='elevation'&&(number<-1000||number>10000))throw Error('elevation must be between -1000 and 10000 metres.');
      result[key]=number;
    }else result[key]=raw;
  }
  if(!editing&&domainKeys.includes(resource)){
    if(!/^\d+$/.test(String(department))||Number(department)<1)throw Error('Select an authorized Department ID.');
    result.department=Number(department);
  }
  return result;
}
export function formatApiError(error){
 const detail=error?.details;
 if(detail&&typeof detail==='object'){
  const parts=Object.entries(detail).map(([field,value])=>`${field}: ${typeof value==='string'?value:JSON.stringify(value)}`);
  if(parts.length)return parts.join('; ');
 }
 return error?.message||'Request failed.';
}
export function safeSpreadsheetText(value){
 const text=String(value==null?'':typeof value==='object'?JSON.stringify(value):value);
 // Quoting CSV is syntax escaping, not protection against formula evaluation.
 return /^[\s\uFEFF]*[=+@-]/u.test(text)||/^[\t\r\n]/u.test(text)?`'${text}`:text;
}
export function csvFromRows(rows,fields){
 const escape=value=>`"${safeSpreadsheetText(value).replaceAll('"','""')}"`;
 return [fields.map(escape).join(','),...rows.map(row=>fields.map(f=>escape(row[f])).join(','))].join('\r\n');
}

export function geographicRecords(lists){
 const label=(kind,id)=>(lists[kind]||[]).find(row=>row.id===id)?.name||String(id??'');
 return {
  'physical-devices':(lists['physical-devices']||[]).map(row=>({...row,
   latitude:row.location?.coordinates?.[1],longitude:row.location?.coordinates?.[0],
   active:row.is_active,type:label('physical-device-types',row.device_type),externalId:`Device #${row.id}`})),
  'network-elements':(lists['network-elements']||[]).map(row=>({...row,
   latitude:row.geometry?.coordinates?.[1],longitude:row.geometry?.coordinates?.[0],
   geometryType:row.geometry?.type||'Point',active:row.is_active,type:label('network-element-types',row.element_type),
   externalId:(row.external_identifiers||[]).map(pair=>`${pair.source}: ${pair.value}`).join(', ')||`Network Element #${row.id}`})),
 };
}
