import {geometryError} from './geometryValidation';
const LEAFLET_JS='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
const LEAFLET_CSS='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
let loader;
export function loadLeaflet(){
  if(window.L?.map)return Promise.resolve(window.L);
  if(loader)return loader;
  loader=new Promise((resolve,reject)=>{
    if(!document.querySelector('[data-leaflet-css]')){
      const link=document.createElement('link');link.rel='stylesheet';link.href=LEAFLET_CSS;link.dataset.leafletCss='true';document.head.appendChild(link);
    }
    const script=document.createElement('script');script.src=LEAFLET_JS;script.async=true;
    script.onload=()=>window.L?.map?resolve(window.L):reject(new Error('Map library could not start'));
    script.onerror=()=>reject(new Error('Map library could not load. Check your internet connection.'));
    document.head.appendChild(script);
  }).catch(error=>{loader=null;throw error});
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
