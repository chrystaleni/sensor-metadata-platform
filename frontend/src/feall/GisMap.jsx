import {useEffect,useMemo,useRef,useState} from 'react';
import './gis.css';

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
        const all=[];
        const walk=(coords)=>{if(!Array.isArray(coords))throw Error('Coordinates must be arrays');if(typeof coords[0]==='number'){
          if(coords.length<2||!Number.isFinite(coords[0])||!Number.isFinite(coords[1])||Math.abs(coords[0])>180||Math.abs(coords[1])>90)throw Error('Invalid WGS84 coordinates');
          all.push(coords);return;
        }coords.forEach(walk)};
        walk(geometry.coordinates);
        if(geometry.type==='Point'&&all.length!==1)throw Error('Invalid point');
        if(geometry.type==='LineString'&&all.length<2)throw Error('Line needs two positions');
        if(geometry.type==='Polygon'&&(!Array.isArray(geometry.coordinates[0])||geometry.coordinates[0].length<4))throw Error('Polygon needs a ring');
        features.push({type:'Feature',geometry,properties:{id:row.id,name:row.name,externalId:row.externalId,kind,type:row.type,active:row.active!==false}});
      }catch{invalid.push(row)}
    }
  }
  return {features,invalid};
}
export default function GisMap({records}){
  const mapElement=useRef(null),mapRef=useRef(null),layerRef=useRef(null),featureLayers=useRef({});
  const [selected,setSelected]=useState(null),[error,setError]=useState(''),[ready,setReady]=useState(false);
  const [kindFilter,setKindFilter]=useState('all'),[showInactive,setShowInactive]=useState(true);
  const {features,invalid}=useMemo(()=>buildMapFeatures(records),[records]);
  const visible=features.filter(f=>(kindFilter==='all'||f.properties.kind===kindFilter)&&(showInactive||f.properties.active));
  const invalidVisible=invalid.filter(row=>{
    const kind=records['physical-devices']?.includes(row)?'Physical Device':'Network Element';
    return (kindFilter==='all'||kindFilter===kind)&&(showInactive||row.active!==false);
  });
  useEffect(()=>{
    let active=true;
    loadLeaflet().then(L=>{
      if(!active||!mapElement.current)return;
      const map=L.map(mapElement.current,{scrollWheelZoom:false}).setView([35.14,33.39],10);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
        attribution:'© OpenStreetMap contributors',maxZoom:19
      }).addTo(map);
      mapRef.current=map;layerRef.current=L.featureGroup().addTo(map);setReady(true);
      requestAnimationFrame(()=>map.invalidateSize());
    }).catch(e=>active&&setError(e.message));
    return ()=>{active=false;if(mapRef.current){mapRef.current.remove();mapRef.current=null}layerRef.current=null};
  },[]);
  useEffect(()=>{
    if(!ready||!mapRef.current||!layerRef.current)return;
    const L=window.L,group=layerRef.current;group.clearLayers();featureLayers.current={};
    for(const feature of visible){
      const p=feature.properties;
      const color=!p.active?'#8997a6':p.kind==='Physical Device'?'#168b83':'#3979c7';
      const layer=L.geoJSON(feature,{
        pointToLayer:(_,latlng)=>L.circleMarker(latlng,{radius:9,color:'#fff',weight:2,fillColor:color,fillOpacity:0.95}),
        style:{color,weight:4,fillColor:color,fillOpacity:0.25}
      });
      layer.on('click',()=>setSelected(p.id));
      layer.bindTooltip(`${p.name} · ${p.kind}`,{sticky:true});
      layer.addTo(group);featureLayers.current[p.id]=layer;
    }
    if(group.getLayers().length&&group.getBounds().isValid())mapRef.current.fitBounds(group.getBounds().pad(0.25),{maxZoom:15,animate:false});
    mapRef.current.invalidateSize();
  },[ready,kindFilter,showInactive,records]);
  const current=visible.find(f=>f.properties.id===selected);
  const fitAll=()=>{const group=layerRef.current;if(group?.getLayers().length&&group.getBounds().isValid())mapRef.current?.fitBounds(group.getBounds().pad(0.25),{maxZoom:15});};
  const focus=(feature)=>{
    setSelected(feature.properties.id);
    const layer=featureLayers.current[feature.properties.id];
    if(layer&&mapRef.current){const bounds=layer.getBounds();if(bounds.isValid())mapRef.current.fitBounds(bounds.pad(0.8),{maxZoom:15});}
  };
  return <section className="fe-panel">
    <div className="fe-panel-head"><div><h2>GIS Map</h2><p>Physical Devices and Network Elements · WGS84 (EPSG:4326)</p></div></div>
    <div className="gis-controls">
      <label>Show <select value={kindFilter} onChange={e=>setKindFilter(e.target.value)}><option value="all">All geographic records</option><option value="Physical Device">Physical Devices</option><option value="Network Element">Network Elements</option></select></label>
      <label className="gis-check"><input type="checkbox" checked={showInactive} onChange={e=>setShowInactive(e.target.checked)}/> Include inactive</label>
      <span>{visible.length} mapped · {invalidVisible.length} missing or invalid</span><button type="button" className="gis-fit" onClick={fitAll} disabled={!ready||!visible.length}>Show all visible</button>
    </div>
    <div className="gis-layout">
      <div className="gis-map-frame">
        <div ref={mapElement} className="gis-map" aria-label="Interactive geographic map"/>
        <div className="gis-legend"><span><i className="gis-dot device"/> Physical device</span><span><i className="gis-dot network"/> Network element</span><span><i className="gis-dot inactive"/> Inactive</span></div>
        {!ready&&!error&&<div className="gis-loading" role="status">Loading interactive map…</div>}
        {error&&<div className="gis-loading" role="alert">{error}. Geographic records are listed alongside the map.</div>}
      </div>
      <aside className="gis-sidebar">
        <h3>Geographic records</h3><p className="gis-muted">Select a record to zoom to its location or shape.</p>
        {visible.length===0&&<p className="gis-muted">No records match these filters.</p>}
        <div className="gis-records">{visible.map(f=><button key={f.properties.id} className={`gis-record ${selected===f.properties.id?'selected':''}`} onClick={()=>focus(f)}>
          <strong>{f.properties.name}</strong><small>{f.properties.kind} · {f.geometry.type} · {f.properties.active?'Active':'Inactive'}</small>
        </button>)}</div>
        {current&&<div className="gis-details"><h3>Selected metadata</h3><dl>
          <dt>Name</dt><dd>{current.properties.name}</dd><dt>Identifier</dt><dd>{current.properties.externalId}</dd>
          <dt>Record type</dt><dd>{current.properties.kind}</dd><dt>Classification</dt><dd>{current.properties.type}</dd>
          <dt>Geometry</dt><dd>{current.geometry.type}</dd><dt>Status</dt><dd>{current.properties.active?'Active':'Inactive'}</dd>
        </dl></div>}
        {invalidVisible.length>0&&<div className="gis-warning"><strong>{invalidVisible.length} record(s) cannot be mapped</strong><p>Missing or invalid WGS84 geographic information:</p><ul>{invalidVisible.map(r=><li key={r.id}>{r.name}</li>)}</ul></div>}
      </aside>
    </div>
    <p className="gis-footnote">Map tiles © OpenStreetMap contributors. Geographic records are sample data until backend integration.</p>
  </section>
}
