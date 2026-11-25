import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import ApiKeys from './ApiKeys';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('displays the raw key only in its creation response and can hide it',async()=>{
 const calls=[];vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{calls.push({url,options});return {ok:true,status:200,json:async()=>options.method==='POST'?{key:'smk_one-time-only'}:[]}}));
 render(<ApiKeys department="7" allowed/>);
 fireEvent.change(screen.getByLabelText('Key name'),{target:{value:'SCADA'}});
 fireEvent.submit(screen.getByLabelText('Key name').closest('form'));
 await screen.findByText('smk_one-time-only');
 expect(JSON.parse(calls.find(c=>c.options.method==='POST').options.body)).toMatchObject({name:'SCADA',department:7});
 fireEvent.click(screen.getByText('Hide key'));expect(screen.queryByText('smk_one-time-only')).not.toBeInTheDocument();
});
it('does not request or expose key management for viewers',()=>{
 const fetch=vi.fn();vi.stubGlobal('fetch',fetch);render(<ApiKeys department="7" allowed={false}/>);
 expect(screen.queryByText('Create API key')).not.toBeInTheDocument();expect(fetch).not.toHaveBeenCalled();
});

it('loads key-management records beyond the first server page',async()=>{
 vi.stubGlobal('fetch',vi.fn(async raw=>{
  const page=Number(new URL(raw).searchParams.get('page'));
  const ids=page===1?Array.from({length:25},(_,i)=>i+1):[26];
  return {ok:true,status:200,json:async()=>({count:26,next:page===1?'next':null,results:ids.map(id=>({id,name:`Key ${id}`,prefix:`prefix${id}`,expires_at:'2099-01-01'}))})};
 }));
 render(<ApiKeys department="7" allowed/>);
 expect(await screen.findByRole('button',{name:'Revoke Key 26',exact:true})).toBeInTheDocument();
});

function keysFetch(calls){const past=new Date(Date.now()-86400000).toISOString(),future=new Date(Date.now()+86400000).toISOString();
 return vi.fn(async(url,options={})=>{calls.push({url:String(url),method:options.method||'GET'});
  return {ok:true,status:options.method==='DELETE'?204:200,json:async()=>(options.method&&options.method!=='GET')?{}:[{id:1,name:'Live',prefix:'a',expires_at:future,revoked_at:null},{id:2,name:'Gone',prefix:'b',expires_at:future,revoked_at:past},{id:3,name:'Old',prefix:'c',expires_at:past,revoked_at:null}]}})}
it('lets System Administrators delete revoked and expired keys',async()=>{
 const calls=[];vi.stubGlobal('fetch',keysFetch(calls));vi.stubGlobal('confirm',()=>true);
 render(<ApiKeys department="7" allowed canDelete/>);
 expect(await screen.findByRole('button',{name:'Revoke Live'})).toBeInTheDocument();
 expect(screen.queryByRole('button',{name:'Delete Live'})).not.toBeInTheDocument();
 expect(screen.getByRole('button',{name:'Revoke Old'})).toBeInTheDocument(); // expired keys can still be revoked (Phase 2, Figure 44)
 expect(screen.queryByRole('button',{name:'Revoke Gone'})).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Delete Gone'}));
 await vi.waitFor(()=>expect(calls.some(c=>c.url.includes('/api-keys/2/purge/')&&c.method==='DELETE')).toBe(true));
 expect(screen.getByRole('button',{name:'Delete Old'})).toBeInTheDocument();
});
it('offers only Revoke to Department Administrators',async()=>{
 vi.stubGlobal('fetch',keysFetch([]));
 render(<ApiKeys department="7" allowed/>);
 await screen.findByRole('button',{name:'Revoke Live'});
 expect(screen.queryByRole('button',{name:/^Delete /})).not.toBeInTheDocument();
});

it('creates a key with no expiration and offers Revoke on expired keys',async()=>{
 const past=new Date(Date.now()-86400000).toISOString();const calls=[];
 vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{calls.push({method:options.method||'GET',body:options.body});
  return {ok:true,status:200,json:async()=>options.method==='POST'?{key:'smk_x'}:[{id:3,name:'Old',prefix:'c',expires_at:past,revoked_at:null},{id:4,name:'Forever',prefix:'d',expires_at:null,revoked_at:null}]}}));
 render(<ApiKeys department="7" allowed/>);
 expect(await screen.findByRole('button',{name:'Revoke Old'})).toBeInTheDocument();
 expect(screen.getByText('Never')).toBeInTheDocument();
 fireEvent.change(screen.getByLabelText('Key name'),{target:{value:'SCADA'}});
 fireEvent.click(screen.getByLabelText('No expiration'));
 expect(screen.getByLabelText('Expiration')).toBeDisabled();
 fireEvent.submit(screen.getByLabelText('Key name').closest('form'));
 await vi.waitFor(()=>expect(calls.some(c=>c.method==='POST')).toBe(true));
 expect(JSON.parse(calls.find(c=>c.method==='POST').body)).toMatchObject({name:'SCADA',department:7,expires_at:null});
});
