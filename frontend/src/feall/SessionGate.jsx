import {useCallback,useEffect,useRef,useState} from 'react';
import {makeApiClient} from './apiClient';
import {csrfToken} from './excelImport';
import {formatApiError} from './backendModel';

const api=makeApiClient({baseUrl:import.meta.env.VITE_API_BASE_URL||'/api/v1',csrf:csrfToken});

export function SessionGate({component:Component}){
 const [session,setSession]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [username,setUsername]=useState(''),[password,setPassword]=useState('');
 const mounted=useRef(false);
 const check=useCallback(async()=>{
  const result=await api('/auth/session/');
  if(!mounted.current)return;
  if(!result.authenticated){setSession(false);return;}
  const context=await api('/auth/context/');
  if(mounted.current)setSession(context.authenticated?context:false);
 },[]);
 useEffect(()=>{
  mounted.current=true;
  queueMicrotask(()=>{void check().catch(e=>{if(mounted.current){setSession(false);setError(formatApiError(e));}});});
  const timer=setInterval(()=>{void check().catch(e=>{if(mounted.current)setError(formatApiError(e));});},30000);
  return()=>{mounted.current=false;clearInterval(timer);};
 },[check]);
 async function login(event){
  event.preventDefault();setBusy(true);setError('');
  try{await api('/auth/csrf/');await api('/auth/login/',{method:'POST',data:{username,password}});setPassword('');await check();}
  catch(e){setError(formatApiError(e));}finally{setBusy(false);}
 }
 async function logout(){
  setError('');try{await api('/auth/csrf/');await api('/auth/logout/',{method:'POST'});setSession(false);setPassword('');}
  catch(e){setError(formatApiError(e));}
 }
 if(session===null)return <p role="status">Restoring session…</p>;
 if(!session)return <main className="all-pad"><h1>Sensor Metadata — Sign in</h1><form onSubmit={login}><label>Username<input autoComplete="username" required value={username} onChange={e=>setUsername(e.target.value)}/></label><label>Password<input type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/></label><button disabled={busy}>{busy?'Signing in…':'Sign in'}</button></form>{error&&<p role="alert">{error}</p>}</main>;
 return <>{error&&<p role="alert">{error}</p>}<Component session={session} onLogout={logout} onSessionCheck={check}/></>;
}
