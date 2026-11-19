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
