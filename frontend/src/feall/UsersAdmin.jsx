import {useCallback,useEffect,useState} from 'react';
import {makeApiClient} from './apiClient';
import {fetchAllPages} from './pagination';
import {csrfToken} from './excelImport';
import {formatApiError} from './backendModel';
import './admin.css';

const api=makeApiClient({baseUrl:import.meta.env.VITE_API_BASE_URL||'/api/v1',csrf:csrfToken});
const ALL_ROLES=[['VIEWER','Viewer'],['EDITOR','Editor'],['DEPARTMENT_ADMIN','Department Administrator'],['SYSTEM_ADMIN','System Administrator']];
const ROLE_NAME=Object.fromEntries(ALL_ROLES);
const blank={username:'',password:'',role:'VIEWER',departments:[]};
// Server rules apply regardless: Department Administrators may assign only Viewer/Editor in their Departments.
export default function UsersAdmin({departments=[],role,allowed,currentUser}){
 const roles=role==='SYSTEM_ADMIN'?ALL_ROLES:ALL_ROLES.slice(0,2);
 const names=Object.fromEntries(departments.map(d=>[d.id,d.name]));
 const [rows,setRows]=useState([]),[form,setForm]=useState(blank),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [reset,setReset]=useState(null),[copied,setCopied]=useState(false);
 const [tick,setTick]=useState(0);const reload=useCallback(()=>setTick(t=>t+1),[]);
 useEffect(()=>{if(!allowed)return;let live=true;const c=new AbortController();
  fetchAllPages(api,'/users/',{signal:c.signal}).then(data=>{if(live)setRows(data)}).catch(e=>{if(live&&e?.name!=='AbortError')setError(formatApiError(e))});
  return()=>{live=false;c.abort()}},[allowed,tick]);
 if(!allowed)return <p>User management requires a Department or System Administrator.</p>;
 const set=(k,v)=>setForm(f=>({...f,[k]:v}));
 async function create(e){e.preventDefault();setBusy(true);setError('');
  try{await api('/users/',{method:'POST',data:{...form,departments:form.departments.map(Number)}});setForm(blank);reload()}
  catch(err){setError(formatApiError(err))}finally{setBusy(false)}}
 async function deactivate(u){setError('');try{await api(`/users/${u.id}/`,{method:'DELETE'});reload()}catch(err){setError(formatApiError(err))}}
 // Reactivate and permanent delete: System Administrators only (also enforced by the server).
 async function reactivate(u){setError('');try{await api(`/users/${u.id}/reactivate/`,{method:'POST'});reload()}catch(err){setError(formatApiError(err))}}
 async function purge(u){if(!window.confirm(`Permanently delete ${u.username}? This cannot be undone. Records they created stay, without their name.`))return;setError('');try{await api(`/users/${u.id}/purge/`,{method:'DELETE'});reload()}catch(err){setError(formatApiError(err))}}

 // System Administrators only (also enforced by the server). Passwords are stored as hashes and can never be
 // shown, so this sets a new random password and displays it once.
 async function confirmReset(e){e.preventDefault();setReset(r=>({...r,busy:true,error:''}));
  try{const result=await api(`/users/${reset.user.id}/reset-password/`,{method:'POST',data:{current_password:reset.current}});
   setReset({user:reset.user,password:result.password,current:'',busy:false,error:''})}
  catch(err){setReset(r=>({...r,busy:false,error:formatApiError(err)}))}}
 function closeReset(){setReset(null);setCopied(false)}
 async function copyPassword(){try{await navigator.clipboard.writeText(reset.password);setCopied(true)}catch{setCopied(false)}}
 return <section className="adm">
  <div className="adm-card">
   <div className="adm-head"><h2>Create user</h2><p>New users sign in with the username and password you set here. Hold Cmd or Ctrl to select several Departments.</p></div>
   <form className="adm-form" onSubmit={create}>
    <label>Username<input required maxLength="150" value={form.username} onChange={e=>set('username',e.target.value)}/></label>
    <label>Password<input required type="password" minLength="12" autoComplete="new-password" placeholder="At least 12 characters" value={form.password} onChange={e=>set('password',e.target.value)}/></label>
    <label>Role<select value={form.role} onChange={e=>set('role',e.target.value)}>{roles.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
    <label>Departments<select multiple value={form.departments} onChange={e=>set('departments',[...e.target.selectedOptions].map(o=>o.value))}>{departments.map(d=><option key={d.id} value={d.id}>{d.organisation} / {d.name}</option>)}</select></label>
    <button className="adm-btn" disabled={busy}>Create user</button>
   </form>
   {error&&<p className="adm-error" role="alert">{error}</p>}
  </div>
  <div className="adm-card">
   <div className="adm-head"><h2>Users</h2></div>
   {rows.length?<table className="adm-table"><thead><tr><th>Username</th><th>Role</th><th>Departments</th><th>Status</th><th/></tr></thead>
    <tbody>{rows.map(u=><tr key={u.id}>
     <td><strong>{u.username}</strong></td><td>{ROLE_NAME[u.role]||'No role'}</td>
     <td>{u.departments.map(id=>names[id]||`#${id}`).join(', ')||'None'}</td>
     <td><span className={`adm-badge ${u.is_active?'ok':'off'}`}>{u.is_active?'Active':'Inactive'}</span></td>
     <td className="actions">{role==='SYSTEM_ADMIN'&&u.username!==currentUser&&<button className="adm-btn ghost" aria-label={`Reset password for ${u.username}`} onClick={()=>{setReset({user:u,current:'',password:'',busy:false,error:''});setCopied(false)}}>Reset password</button>}{u.is_active
      ?<button className="adm-btn ghost danger" aria-label={`Deactivate ${u.username}`} onClick={()=>deactivate(u)}>Deactivate</button>
      :role==='SYSTEM_ADMIN'&&<><button className="adm-btn ghost" aria-label={`Reactivate ${u.username}`} onClick={()=>reactivate(u)}>Reactivate</button><button className="adm-btn ghost danger" aria-label={`Delete ${u.username}`} onClick={()=>purge(u)}>Delete</button></>}</td></tr>)}</tbody></table>
    :<p className="adm-empty">No users to show.</p>}
  </div>
  {reset&&<div className="all-overlay"><section className="all-dialog" role="dialog" aria-modal="true" aria-label={`Reset password for ${reset.user.username}`}>
   <header><h2>Reset password</h2><button type="button" onClick={closeReset} aria-label="Close">×</button></header>
   {reset.password
    ?<div style={{padding:16}}>
      <p>New password for <strong>{reset.user.username}</strong>. It is shown only once. Copy it now and give it to the user; the old password no longer works.</p>
      <p><code aria-label="New password" style={{fontSize:18,padding:'8px 10px',background:'#eef2f3',borderRadius:6,userSelect:'all'}}>{reset.password}</code></p>
      <p><button type="button" className="all-secondary" onClick={copyPassword}>{copied?'Copied':'Copy password'}</button></p>
      <footer><button type="button" className="all-primary" onClick={closeReset}>Done</button></footer>
     </div>
    :<form style={{padding:16}} onSubmit={confirmReset}>
      <p>A new random password will be created for <strong>{reset.user.username}</strong>. The old password stops working and the user is signed out. Enter your own password to continue.</p>
      <label>Your password<input required autoFocus type="password" autoComplete="current-password" value={reset.current} onChange={e=>setReset(r=>({...r,current:e.target.value}))}/></label>
      {reset.error&&<p className="adm-error" role="alert">{reset.error}</p>}
      <footer><button type="button" className="all-secondary" onClick={closeReset}>Cancel</button><button className="all-primary" disabled={reset.busy||!reset.current}>Reset password</button></footer>
     </form>}
  </section></div>}
 </section>;
}
