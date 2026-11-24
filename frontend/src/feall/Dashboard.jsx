import {useEffect,useState} from 'react';
import {breakdown,geometryKinds,recentActivity,completeness,relativeTime} from './dashboardStats';

const KINDS={measurements:'Measurement','physical-devices':'Physical device','network-elements':'Network element'};
function Bars({title,rows,empty='No data yet.'}){
 const max=Math.max(1,...rows.map(r=>r.count));
 return <section className="fe-panel dash-card"><div className="fe-panel-head"><h2>{title}</h2></div>
  {rows.length?<ul className="dash-bars">{rows.map(r=><li key={r.label}><span className="dash-bar-label">{r.label}</span>
   <span className="dash-bar-track"><span className="dash-bar-fill" style={{width:`${(r.count/max)*100}%`}}/></span><b>{r.count}</b></li>)}</ul>:<p className="dash-empty">{empty}</p>}</section>;
}
const pct=(n,d)=>d?`${Math.round((n/d)*100)}%`:'—';

export default function Dashboard({lists,departments=[],api}){
 const [byDepartment,setByDepartment]=useState(null);
 const ids=departments.map(d=>d.id).join(',');
 useEffect(()=>{
  if(!api||!departments.length)return;
  let live=true;const c=new AbortController();
  const count=(path,id)=>api(path,{params:{department:id,page_size:1},signal:c.signal}).then(r=>r?.count??r?.results?.length??0);
  Promise.all(departments.map(async d=>({
   id:d.id,label:`${d.organisation} / ${d.name}`,
   measurements:await count('/measurements/',d.id),devices:await count('/physical-devices/',d.id),elements:await count('/network-elements/',d.id),
  }))).then(rows=>{if(live)setByDepartment(rows)}).catch(()=>{if(live)setByDepartment([])});
  return()=>{live=false;c.abort()};
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[api,ids]);
 const m=lists.measurements||[],d=lists['physical-devices']||[],e=lists['network-elements']||[];
 const c=completeness(lists),recent=recentActivity(lists,KINDS);
 const tiles=[['Measurements',m.length],['Physical Devices',d.length],['Network Elements',e.length],['On the map',`${c.mapped}/${c.mappable}`]];
 return <div className="dash">
  <div className="fe-stat-grid dash-tiles">{tiles.map(([name,value])=><div className="fe-stat" key={name}><strong>{value}</strong><div>{name}</div></div>)}</div>
  <div className="dash-grid">
   <Bars title="Measurements by type" rows={breakdown(m,'measurement_type',lists['measurement-types'])}/>
   <Bars title="Devices by type" rows={breakdown(d,'device_type',lists['physical-device-types'])}/>
   <Bars title="Network elements by type" rows={breakdown(e,'element_type',lists['network-element-types'])}/>
   <Bars title="Map geometry" rows={geometryKinds(e)}/>
  </div>
  <div className="dash-grid">
   <section className="fe-panel dash-card"><div className="fe-panel-head"><h2>Recently updated</h2></div>
    {recent.length?<ul className="dash-recent">{recent.map(r=><li key={`${r.key}-${r.id}`}><span><strong>{r.name}</strong><small>{r.kind}{r.created?' · new':' · updated'}</small></span><time dateTime={r.at}>{relativeTime(r.at)}</time></li>)}</ul>:<p className="dash-empty">Nothing recorded yet.</p>}</section>
   <section className="fe-panel dash-card"><div className="fe-panel-head"><h2>Data quality</h2></div>
    <ul className="dash-quality">
     <li><span>Measurements with a collection configuration</span><b>{pct(c.withConfig,c.measurements)}</b></li>
     <li><span>Measurements with customer or meter account</span><b>{pct(c.withAccounts,c.measurements)}</b></li>
     <li><span>Devices and elements placed on the map</span><b>{pct(c.mapped,c.mappable)}</b></li>
    </ul></section>
  </div>
  {departments.length>1&&<section className="fe-panel dash-card"><div className="fe-panel-head"><h2>By Department</h2></div>
   {byDepartment===null?<p className="dash-empty">Loading…</p>:<table className="dash-table"><thead><tr><th>Department</th><th>Measurements</th><th>Devices</th><th>Network elements</th></tr></thead>
    <tbody>{byDepartment.map(r=><tr key={r.id}><td>{r.label}</td><td>{r.measurements}</td><td>{r.devices}</td><td>{r.elements}</td></tr>)}</tbody></table>}</section>}
 </div>;
}
