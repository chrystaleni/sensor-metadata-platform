import {useEffect,useState} from 'react';
import {fetchAllPages} from './pagination';
import {formatApiError} from './backendModel';
import './admin.css';
import {ROLE_NAME,ROLE_ABOUT,DEFAULT_DEPARTMENT_KEY,readDefaultDepartment} from './settingsModel';


function Card({title,about,children}){return <div className="adm-card"><div className="adm-head"><h2>{title}</h2>{about&&<p>{about}</p>}</div>{children}</div>}
function Message({error,ok}){return <>{error&&<p className="adm-error" role="alert">{error}</p>}{ok&&<p className="adm-ok" role="status">{ok}</p>}</>}

function Account({session}){
 return <Card title="My account" about={ROLE_ABOUT[session.role]||'No role is assigned to your account yet. Ask an administrator.'}>
  <dl className="adm-facts">
   <div><dt>Username</dt><dd>{session.user?.username||'—'}</dd></div>
   <div><dt>Role</dt><dd>{ROLE_NAME[session.role]||'None'}</dd></div>
   <div><dt>Departments</dt><dd>{session.departments.length?session.departments.map(d=>`${d.organisation} / ${d.name}${d.writable?'':' (read-only)'}`).join(', '):'None'}</dd></div>
  </dl></Card>;
}

function Password({api}){
 const [v,setV]=useState({current:'',next:'',again:''}),[busy,setBusy]=useState(false),[error,setError]=useState(''),[ok,setOk]=useState('');
 async function submit(e){e.preventDefault();setError('');setOk('');
  if(v.next!==v.again){setError('The new passwords do not match.');return}
  setBusy(true);
  try{await api('/auth/csrf/');await api('/auth/password/',{method:'POST',data:{current_password:v.current,new_password:v.next}});setV({current:'',next:'',again:''});setOk('Password changed. Other devices have been signed out.')}
  catch(err){const d=err?.details;setError(d?.current_password?.[0]||d?.new_password?.join(' ')||formatApiError(err))}finally{setBusy(false)}}
 const bind=k=>({value:v[k],onChange:e=>setV(s=>({...s,[k]:e.target.value})),type:'password',required:true});
 return <Card title="Change password" about="Use at least 12 characters. You stay signed in on this device.">
  <form className="adm-form" onSubmit={submit}>
   <label>Current password<input {...bind('current')} autoComplete="current-password"/></label>
   <label>New password<input {...bind('next')} minLength="12" autoComplete="new-password"/></label>
   <label>Confirm new password<input {...bind('again')} minLength="12" autoComplete="new-password"/></label>
   <button className="adm-btn" disabled={busy}>Change password</button>
  </form><Message error={error} ok={ok}/></Card>;
}

function Preferences({departments,department,onDepartment}){
 const [saved,setSaved]=useState(readDefaultDepartment);
 function choose(id){setSaved(id);try{id?localStorage.setItem(DEFAULT_DEPARTMENT_KEY,id):localStorage.removeItem(DEFAULT_DEPARTMENT_KEY)}catch{/* storage unavailable: preference is session-only */}if(id)onDepartment(id)}
 return <Card title="Preferences" about="Stored in this browser only.">
  <div className="adm-form"><label>Default Department
   <select value={saved} onChange={e=>choose(e.target.value)}><option value="">First available</option>{departments.map(d=><option key={d.id} value={d.id}>{d.organisation} / {d.name}</option>)}</select></label>
   <p className="adm-hint">Currently working in: <strong>{departments.find(d=>String(d.id)===String(department))?.name||'none selected'}</strong></p></div></Card>;
}

function DepartmentAdmin({departments}){
 return <Card title="Department administration" about="Manage the people and integrations of the Departments you administer.">
  <div className="adm-links"><a className="adm-btn ghost" href="#/administration">Manage users</a><a className="adm-btn ghost" href="#/api-keys">Manage API keys</a></div>
  <table className="adm-table"><thead><tr><th>Department</th><th>Organisation</th></tr></thead><tbody>{departments.map(d=><tr key={d.id}><td><strong>{d.name}</strong></td><td>{d.organisation}</td></tr>)}</tbody></table></Card>;
}

function Organisations({api,onChanged}){
 const [orgs,setOrgs]=useState([]),[deps,setDeps]=useState([]),[tick,setTick]=useState(0),[error,setError]=useState(''),[ok,setOk]=useState('');
 const [org,setOrg]=useState({name:'',code:''}),[dep,setDep]=useState({name:'',organisation:''});
 useEffect(()=>{let live=true;const c=new AbortController();
  Promise.all([fetchAllPages(api,'/organisations/',{signal:c.signal}),fetchAllPages(api,'/departments/',{signal:c.signal})])
   .then(([o,d])=>{if(live){setOrgs(o);setDeps(d)}}).catch(e=>{if(live&&e?.name!=='AbortError')setError(formatApiError(e))});
  return()=>{live=false;c.abort()}},[api,tick]);
 async function add(path,data,reset,label){setError('');setOk('');
  try{await api(path,{method:'POST',data});reset();setTick(t=>t+1);setOk(`${label} created. Add users to it from the Administration page.`);onChanged?.()}
  catch(err){const d=err?.details;setError(d&&typeof d==='object'?Object.values(d).flat().join(' '):formatApiError(err))}}
 return <Card title="Organisations and Departments" about="Organisations group Departments. Each Department owns its operational records.">
  <form className="adm-form" onSubmit={e=>{e.preventDefault();add('/organisations/',org,()=>setOrg({name:'',code:''}),'Organisation')}}>
   <label>Organisation name<input required value={org.name} onChange={e=>setOrg(o=>({...o,name:e.target.value}))}/></label>
   <label>Code<input required pattern="[a-z0-9_-]+" placeholder="lowercase-code" value={org.code} onChange={e=>setOrg(o=>({...o,code:e.target.value}))}/></label>
   <button className="adm-btn">Add Organisation</button></form>
  <form className="adm-form" onSubmit={e=>{e.preventDefault();add('/departments/',{name:dep.name,organisation:Number(dep.organisation)},()=>setDep({name:'',organisation:''}),'Department')}}>
   <label>Department name<input required value={dep.name} onChange={e=>setDep(d=>({...d,name:e.target.value}))}/></label>
   <label>Organisation<select required value={dep.organisation} onChange={e=>setDep(d=>({...d,organisation:e.target.value}))}><option value="">Select…</option>{orgs.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
   <button className="adm-btn">Add Department</button></form>
  <Message error={error} ok={ok}/>
  <table className="adm-table"><thead><tr><th>Organisation</th><th>Departments</th></tr></thead><tbody>{orgs.map(o=><tr key={o.id}><td><strong>{o.name}</strong> <span className="adm-mono">{o.code}</span></td><td>{deps.filter(d=>d.organisation===o.id).map(d=>d.name).join(', ')||'None'}</td></tr>)}</tbody></table></Card>;
}

export default function Settings({session,api,department,onDepartment,pickable}){
 const role=session.role;
 return <section className="adm">
  <Account session={session}/>
  <Password api={api}/>
  <Preferences departments={pickable} department={department} onDepartment={onDepartment}/>
  {(role==='DEPARTMENT_ADMIN'||role==='SYSTEM_ADMIN')&&<DepartmentAdmin departments={session.departments}/>}
  {role==='SYSTEM_ADMIN'&&<Organisations api={api}/>}
 </section>;
}
