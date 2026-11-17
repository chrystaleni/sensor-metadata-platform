export const definitions={
'measurements':{label:'Measurements',fields:[['externalId','Measurement ID','text',true],['name','Measurement name','text',true],['type','Measurement type','select',true,['Flow','Pressure','Level','Quality']],['unit','Measurement unit','select',true,['m³/h','bar','m','mg/L']],['device','Physical device','relation-device',true],['network','Network element','relation-network',true],['customerAccount','Customer Account','text'],['meterAccount','Meter Account','text'],['details','Details','textarea']]},
'physical-devices':{label:'Physical Devices',fields:[['externalId','Device ID','text',true],['name','Device name','text',true],['type','Device type','select',true,['RTU','Sensor','Logger','Meter']],['latitude','Latitude','number'],['longitude','Longitude','number'],['manufacturer','Manufacturer','text']]},
'network-elements':{label:'Network Elements',fields:[['externalId','Network element ID','text',true],['name','Network element name','text',true],['type','Element type','select',true,['Pipe','Valve','Reservoir','Station']],['geometryType','Geometry type','select',true,['Point','LineString','Polygon']],['latitude','Latitude (point)','number'],['longitude','Longitude (point)','number'],['geometry','GeoJSON geometry (line/polygon)','textarea'],['dmaModel','DMA Model ID','text'],['strategicModel','Strategic Model ID','text'],['externalIdentifiers','Other external identifiers','textarea']]}}
export const initialData={
'measurements':[{id:'m1',externalId:'DEMO-M001',name:'Flow at Station A',type:'Flow',unit:'m³/h',device:'d1',network:'n1',active:true},{id:'m2',externalId:'DEMO-M002',name:'Pressure at Station B',type:'Pressure',unit:'bar',device:'d2',network:'n2',active:true},{id:'m3',externalId:'DEMO-M003',name:'Reservoir level',type:'Level',unit:'m',device:'d1',network:'n2',active:false}],
'physical-devices':[{id:'d1',externalId:'DEMO-D001',name:'RTU Station A',type:'RTU',latitude:'35.16',longitude:'33.36',manufacturer:'Demo',active:true},{id:'d2',externalId:'DEMO-D002',name:'Sensor Station B',type:'Sensor',latitude:'35.11',longitude:'33.42',manufacturer:'Demo',active:true}],
'network-elements':[{id:'n1',externalId:'DEMO-N001',name:'Station A',type:'Station',geometryType:'Point',latitude:'35.16',longitude:'33.36',active:true},{id:'n2',externalId:'DEMO-N002',name:'Reservoir B',type:'Reservoir',geometryType:'Point',latitude:'35.11',longitude:'33.42',active:true}]}
export const cloneData=()=>Object.fromEntries(Object.entries(initialData).map(([key,rows])=>[key,rows.map(row=>({...row}))]));
export function validateRecord(kind,record,all,editingId){
 const def=definitions[kind];
 for(const [key,label,,required] of def.fields){
   if(required&&!String(record[key]??'').trim())return `${label} is required.`;
 }
 const id=String(record.externalId??'').trim().toLowerCase();
 const name=String(record.name??'').trim().toLowerCase();
 if(all[kind].some(row=>row.id!==editingId&&String(row.externalId??'').trim().toLowerCase()===id))return 'This identifier already exists.';
 if(all[kind].some(row=>row.id!==editingId&&String(row.name??'').trim().toLowerCase()===name))return 'This name already exists.';
 if(kind==='measurements'){
   for(const [field,table] of [['device','physical-devices'],['network','network-elements']]){
     if(!all[table].some(row=>row.id===record[field]&&row.active))return `Choose an active ${field==='device'?'Physical Device':'Network Element'}.`;
   }
 }
 if(kind==='physical-devices'||kind==='network-elements'){
   const point=kind==='physical-devices'||(record.geometryType||'Point')==='Point';
   if(point){
     const lat=String(record.latitude??'').trim(),lon=String(record.longitude??'').trim();
     if(Boolean(lat)!==Boolean(lon))return 'Provide both latitude and longitude.';
     if(lat&&(!Number.isFinite(Number(lat))||Number(lat)<-90||Number(lat)>90))return 'Latitude must be between -90 and 90.';
     if(lon&&(!Number.isFinite(Number(lon))||Number(lon)<-180||Number(lon)>180))return 'Longitude must be between -180 and 180.';
   }
 }
 if(kind==='network-elements'&&record.geometryType&&record.geometryType!=='Point'){
   if(!String(record.geometry??'').trim())return 'Select geometry on the map or enter GeoJSON.';
   try{
     const geo=JSON.parse(record.geometry);
     if(geo.type!==record.geometryType||!Array.isArray(geo.coordinates))return 'GeoJSON type/coordinates do not match the selected geometry.';
     const positions=[];
     const walk=x=>{if(typeof x?.[0]==='number'){positions.push(x);return}if(!Array.isArray(x))throw Error('Invalid coordinates');x.forEach(walk)};
     walk(geo.coordinates);
     if(!positions.length||positions.some(p=>p.length<2||!Number.isFinite(p[0])||!Number.isFinite(p[1])||Math.abs(p[0])>180||Math.abs(p[1])>90))return 'Coordinates must be valid WGS84 longitude/latitude pairs.';
     if(geo.type==='LineString'&&positions.length<2)return 'A line requires at least two points.';
     if(geo.type==='Polygon'&&(!Array.isArray(geo.coordinates[0])||geo.coordinates[0].length<4||JSON.stringify(geo.coordinates[0][0])!==JSON.stringify(geo.coordinates[0].at(-1))))return 'A polygon requires a closed ring of at least four positions.';
   }catch{return 'Enter valid GeoJSON geometry.'}
 }
 return '';
}
