import {useCallback,useEffect,useRef,useState} from 'react';
import {makeApiClient} from './apiClient';
import {csrfToken} from './excelImport';
import {formatApiError} from './backendModel';
import './SessionGate.css';

const api=makeApiClient({baseUrl:import.meta.env.VITE_API_BASE_URL||'/api/v1',csrf:csrfToken});

export function SessionGate({component:Component}){
 const [session,setSession]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [username,setUsername]=useState(''),[password,setPassword]=useState('');
 const [showPassword,setShowPassword]=useState(false);
 const mounted=useRef(false);
 const check=useCallback(async()=>{
  const result=await api('/auth/session/');
  if(!mounted.current)return;
  if(!result.authenticated){setSession(false);return;}
  const context=await api('/auth/context/');
  if(mounted.current)setSession(context.authenticated?{...context,user:result.user}:false);
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
 if(session===null)return <main className="login-page"><p role="status" className="login-loading">Restoring session…</p></main>;
 if(!session)return <main className="login-page">
  <section className="login-card" aria-label="Sign in to Sensor Metadata Management Platform">
   <div className="login-logo" aria-hidden="true">SM</div>
   <div className="login-eyebrow">SENSOR METADATA MANAGEMENT</div>
   <h1>Welcome back</h1>
   <p className="login-intro">Sign in to manage your department’s sensor metadata.</p>
   {error&&<div className="login-error" role="alert">{error}</div>}
   <form className="login-form" onSubmit={login}>
    <label htmlFor="login-username">Username</label>
    <input id="login-username" name="username" autoComplete="username" required value={username} onChange={e=>setUsername(e.target.value)} placeholder="Enter your username"/>
    <label htmlFor="login-password">Password</label>
    <div className="login-password-field">
     <input id="login-password" name="password" type={showPassword?'text':'password'} autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your password"/>
     <button className="login-show-password" type="button" aria-label={showPassword?'Hide password':'Show password'} aria-pressed={showPassword} onClick={()=>setShowPassword(v=>!v)}>{showPassword?'Hide':'Show'}</button>
    </div>
    <button className="login-submit" type="submit" disabled={busy}>{busy?'Signing in…':'Sign in'}<span aria-hidden="true">→</span></button>
   </form>
   <footer className="login-footer">Sensor Metadata Management Platform</footer>
  </section>
 </main>;
 return <>{error&&<p role="alert">{error}</p>}<Component key={JSON.stringify([session.role,session.departments,session.permissions])} session={session} onLogout={logout} onSessionCheck={check}/></>;
}
