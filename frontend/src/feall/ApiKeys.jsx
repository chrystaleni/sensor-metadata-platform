import {useCallback,useEffect,useState} from 'react';
import {makeApiClient} from './apiClient';
import {fetchAllPages} from './pagination';
import {csrfToken} from './excelImport';
import {formatApiError} from './backendModel';

const api=makeApiClient({baseUrl:import.meta.env.VITE_API_BASE_URL||'/api/v1',csrf:csrfToken});
export default function ApiKeys({department,allowed}){
 const [rows,setRows]=useState([]),[name,setName]=useState(''),[expires,setExpires]=useState('');
 const [raw,setRaw]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const reload=useCallback(async()=>{const data=await fetchAllPages(api,'/api-keys/',{params:{department}});setRows(data);},[department]);
 useEffect(()=>{let live=true;const controller=new AbortController();if(allowed&&department)fetchAllPages(api,'/api-keys/',{params:{department},signal:controller.signal}).then(data=>{if(live)setRows(data)}).catch(e=>{if(live)setError(formatApiError(e))});return()=>{live=false;controller.abort()}},[allowed,department]);
 async function create(e){e.preventDefault();setBusy(true);setError('');setRaw('');try{const data=await api('/api-keys/',{method:'POST',data:{name,department:Number(department),...(expires?{expires_at:new Date(expires).toISOString()}:{})}});setRaw(data.key);setName('');await reload();}catch(e){setError(formatApiError(e))}finally{setBusy(false)}}
 async function revoke(id){setError('');try{await api(`/api-keys/${id}/`,{method:'DELETE'});await reload()}catch(e){setError(formatApiError(e))}}
 if(!allowed||!department)return <p>API key management requires a Department or System Administrator and an authorized Department.</p>;
 return <section><h2>Department API keys</h2><p>Read-only access to the selected Department. Keys expire after 90 days unless a different future expiration is specified.</p><form onSubmit={create}><label>Key name<input required maxLength="120" value={name} onChange={e=>setName(e.target.value)}/></label><label>Expiration<input type="datetime-local" value={expires} onChange={e=>setExpires(e.target.value)}/></label><button disabled={busy}>Create API key</button></form>{raw&&<div role="status"><p>Copy this key now. It will not be displayed again.</p><code>{raw}</code><button onClick={()=>setRaw('')}>Hide key</button></div>}{error&&<p role="alert">{error}</p>}<ul>{rows.map(row=><li key={row.id}>{row.name} — {row.prefix} — expires {row.expires_at}{row.revoked_at?' — revoked':<button onClick={()=>revoke(row.id)}>Revoke {row.name}</button>}</li>)}</ul></section>;
}
