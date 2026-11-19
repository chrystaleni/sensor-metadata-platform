import {geometryError} from './geometryValidation';
import 'leaflet/dist/leaflet.css';
let loader;
export function loadLeaflet(){
  if(window.L?.map)return Promise.resolve(window.L);
  if(!loader)loader=import('leaflet').then(module=>{window.L=module.default||module;return window.L;}).catch(error=>{loader=null;throw error});
  return loader;
}
function pointCoordinates(row){
  const lat=Number(row.latitude),lng=Number(row.longitude);
  if(String(row.latitude??'').trim()===''||String(row.longitude??'').trim()===''||!Number.isFinite(lat)||!Number.isFinite(lng)||Math.abs(lat)>90||Math.abs(lng)>180)return null;
  return [lat,lng];
}
export function buildMapFeatures(records){
  const features=[],invalid=[];
  for(const [kind,rows] of [['Physical Device',records['physical-devices']||[]],['Network Element',records['network-elements']||[]]]){
    for(const row of rows){
      let geometry;
      if(kind==='Physical Device'||!row.geometryType||row.geometryType==='Point'){
        const pair=pointCoordinates(row);
        if(pair)geometry={type:'Point',coordinates:[pair[1],pair[0]]};
      }else{
        try{
          const raw=typeof row.geometry==='string'?JSON.parse(row.geometry):row.geometry;
          geometry=raw?.type==='Feature'?raw.geometry:raw;
          if(!geometry||geometry.type!==row.geometryType||!Array.isArray(geometry.coordinates))geometry=null;
        }catch{geometry=null}
      }
      if(!geometry){invalid.push(row);continue}
      try{
        if(geometryError(geometry))throw Error('Invalid GeoJSON geometry');
        features.push({type:'Feature',geometry,properties:{id:row.id,name:row.name,externalId:row.externalId,kind,type:row.type,active:row.active!==false}});
      }catch{invalid.push(row)}
    }
  }
  return {features,invalid};
}

// Database IDs are unique per table, not across geographic resources.
export const featureKey = feature => `${feature.properties.kind}:${feature.properties.id}`;
