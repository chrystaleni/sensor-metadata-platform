import {useCallback,useEffect,useState} from 'react';
import {makeApiClient} from './apiClient';
import {fetchAllPages} from './pagination';
import {csrfToken} from './excelImport';
import {formatApiError} from './backendModel';
import './admin.css';

const api=makeApiClient({baseUrl:import.meta.env.VITE_API_BASE_URL||'/api/v1',csrf:csrfToken});
const when=iso=>iso?new Date(iso).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}):'Never';
function status(row,now=Date.now()){
 if(row.revoked_at)return ['Revoked','off'];
 if(row.expires_at&&new Date(row.expires_at)<=now)return ['Expired','warn'];
 return ['Active','ok'];
}
export default function ApiKeys({department,allowed}){
 const [rows,setRows]=useState([]),[name,setName]=useState(''),[expires,setExpires]=useState('');
 const [raw,setRaw]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[copied,setCopied]=useState(false);
 const reload=useCallback(async()=>{const data=await fetchAllPages(api,'/api-keys/',{params:{department}});setRows(data);},[department]);
 useEffect(()=>{let live=true;const controller=new AbortController();if(allowed&&department)fetchAllPages(api,'/api-keys/',{params:{department},signal:controller.signal}).then(data=>{if(live)setRows(data)}).catch(e=>{if(live)setError(formatApiError(e))});return()=>{live=false;controller.abort()}},[allowed,department]);
 async function create(e){e.preventDefault();setBusy(true);setError('');setRaw('');setCopied(false);try{const data=await api('/api-keys/',{method:'POST',data:{name,department:Number(department),...(expires?{expires_at:new Date(expires).toISOString()}:{})}});setRaw(data.key);setName('');setExpires('');await reload();}catch(e){setError(formatApiError(e))}finally{setBusy(false)}}
 async function revoke(id){setError('');try{await api(`/api-keys/${id}/`,{method:'DELETE'});await reload()}catch(e){setError(formatApiError(e))}}
 async function copy(){try{await navigator.clipboard.writeText(raw);setCopied(true)}catch{setCopied(false)}}
 if(!allowed||!department)return <p>API key management requires a Department or System Administrator and an authorized Department.</p>;
 return <section className="adm">
  <div className="adm-card">
   <div className="adm-head"><h2>Department API keys</h2><p>Read-only access to the selected Department. Keys expire after 90 days unless a different future expiration is specified.</p></div>
   <form className="adm-form" onSubmit={create}>
    <label>Key name<input required maxLength="120" placeholder="e.g. SCADA integration" value={name} onChange={e=>setName(e.target.value)}/></label>
    <label>Expiration<input type="datetime-local" value={expires} onChange={e=>setExpires(e.target.value)}/></label>
    <button className="adm-btn" disabled={busy}>Create API key</button>
   </form>
   {raw&&<div className="adm-secret" role="status"><p>Copy this key now. It will not be displayed again.</p><code>{raw}</code>
    <div><button type="button" className="adm-btn ghost" onClick={copy}>{copied?'Copied':'Copy key'}</button><button type="button" className="adm-btn ghost" onClick={()=>setRaw('')}>Hide key</button></div></div>}
   {error&&<p className="adm-error" role="alert">{error}</p>}
  </div>
  <div className="adm-card">
   {rows.length?<table className="adm-table"><thead><tr><th>Name</th><th>Prefix</th><th>Status</th><th>Expires</th><th/></tr></thead>
    <tbody>{rows.map(row=>{const [label,tone]=status(row);return <tr key={row.id}>
     <td><strong>{row.name}</strong></td><td className="adm-mono">{row.prefix}</td>
     <td><span className={`adm-badge ${tone}`}>{label}</span></td><td>{when(row.expires_at)}</td>
     <td className="actions">{!row.revoked_at&&<button className="adm-btn ghost danger" aria-label={`Revoke ${row.name}`} onClick={()=>revoke(row.id)}>Revoke</button>}</td></tr>})}</tbody></table>
    :<p className="adm-empty">No API keys for this Department yet.</p>}
  </div>
 </section>;
}
