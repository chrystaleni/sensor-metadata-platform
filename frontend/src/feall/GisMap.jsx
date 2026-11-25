import {loadGreekMapStyle,addGreekBasemap} from './greekBasemap';
import {useEffect,useMemo,useRef,useState} from 'react';
import './gis.css';

import {loadLeaflet,buildMapFeatures,featureKey} from './mapUtils';

// Default view: Cyprus around Nicosia.
const DEFAULT_VIEW={center:[35.14,33.39],zoom:10};
export default function GisMap({records}){
  const mapElement=useRef(null),mapRef=useRef(null),layerRef=useRef(null),featureLayers=useRef({});
  const [selected,setSelected]=useState(null),[error,setError]=useState(''),[ready,setReady]=useState(false);
  const [kindFilter,setKindFilter]=useState('all'),[showInactive,setShowInactive]=useState(true);
  const {features,invalid}=useMemo(()=>buildMapFeatures(records),[records]);
  const visible=useMemo(()=>features.filter(f=>(kindFilter==='all'||f.properties.kind===kindFilter)&&(showInactive||f.properties.active)),[features,kindFilter,showInactive]);
  const invalidVisible=invalid.filter(row=>{
    const kind=records['physical-devices']?.includes(row)?'Physical Device':'Network Element';
    return (kindFilter==='all'||kindFilter===kind)&&(showInactive||row.active!==false);
  });
  useEffect(()=>{
    let active=true;
    Promise.all([loadLeaflet(),loadGreekMapStyle()]).then(([L,style])=>{
      if(!active||!mapElement.current)return;
      const map=L.map(mapElement.current,{scrollWheelZoom:false,minZoom:1,maxZoom:19}).setView(DEFAULT_VIEW.center,DEFAULT_VIEW.zoom);
      addGreekBasemap(map,style);
      map.attributionControl.addAttribution('© OpenStreetMap contributors | OpenFreeMap');
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
        pointToLayer:(_,latlng)=>L.circleMarker(latlng,{radius:8,stroke:false,fillColor:color,fillOpacity:0.55}),
        style:(f)=>f.geometry.type==='Point'?{stroke:false,fillColor:color,fillOpacity:0.6}:{color,weight:4,fillColor:color,fillOpacity:0.25}
      });
      layer.on('click',()=>setSelected(featureKey(feature)));
      const tooltipText=document.createTextNode(`${p.name} · ${p.kind}`);
      layer.bindTooltip(tooltipText,{sticky:true});
      layer.addTo(group);featureLayers.current[featureKey(feature)]=layer;
    }
    if(group.getLayers().length&&group.getBounds().isValid())mapRef.current.fitBounds(group.getBounds().pad(0.25),{maxZoom:15,animate:false});
    // Nothing to show (e.g. an empty Department): go back to the default view instead of keeping the previous area.
    else mapRef.current.setView(DEFAULT_VIEW.center,DEFAULT_VIEW.zoom,{animate:false});
    mapRef.current.invalidateSize();
  },[ready,visible]);
  const current=visible.find(f=>featureKey(f)===selected);
  const fitAll=()=>{const group=layerRef.current;if(group?.getLayers().length&&group.getBounds().isValid())mapRef.current?.fitBounds(group.getBounds().pad(0.25),{maxZoom:15});};
  const focus=(feature)=>{
    setSelected(featureKey(feature));
    const layer=featureLayers.current[featureKey(feature)];
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
        <div className="gis-records">{visible.map(f=><button key={featureKey(f)} className={`gis-record ${selected===featureKey(f)?'selected':''}`} onClick={()=>focus(f)}>
          <strong>{f.properties.name}</strong><small>{f.properties.kind} · {f.geometry.type} · {f.properties.active?'Active':'Inactive'}</small>
        </button>)}</div>
        {current&&<div className="gis-details"><h3>Selected metadata</h3><dl>
          <dt>Name</dt><dd>{current.properties.name}</dd><dt>Identifier</dt><dd>{current.properties.externalId}</dd>
          <dt>Record type</dt><dd>{current.properties.kind}</dd><dt>Classification</dt><dd>{current.properties.type}</dd>
          <dt>Geometry</dt><dd>{current.geometry.type}</dd><dt>Status</dt><dd>{current.properties.active?'Active':'Inactive'}</dd>
        </dl></div>}
        {invalidVisible.length>0&&<div className="gis-warning"><strong>{invalidVisible.length} record(s) cannot be mapped</strong><p>Missing or invalid WGS84 geographic information:</p><ul>{invalidVisible.map(r=><li key={`${records['physical-devices']?.includes(r)?'device':'network'}:${r.id}`}>{r.name}</li>)}</ul></div>}
      </aside>
    </div>
    <p className="gis-footnote">Map tiles © OpenStreetMap contributors. Geographic records come from the authorized backend dataset. Basemap tiles require internet access.</p>
  </section>
}
