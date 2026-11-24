import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import UsersAdmin from './UsersAdmin';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const depts=[{id:7,name:'North',organisation:'Water'}];
it('creates a user with role and Departments, then lists users',async()=>{
 const calls=[];vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{calls.push({url,options});
  return {ok:true,status:200,json:async()=>options.method==='POST'?{id:2}:[{id:1,username:'ann',role:'EDITOR',departments:[7],is_active:true}]}}));
 render(<UsersAdmin departments={depts} role="SYSTEM_ADMIN" allowed/>);
 expect(await screen.findByText('ann')).toBeInTheDocument();expect(screen.getByText('Editor',{selector:'td'})).toBeInTheDocument();
 fireEvent.change(screen.getByLabelText('Username'),{target:{value:'bob'}});
 fireEvent.change(screen.getByLabelText('Password'),{target:{value:'a-long-test-passphrase'}});
 fireEvent.change(screen.getByLabelText('Role'),{target:{value:'EDITOR'}});
 fireEvent.submit(screen.getByLabelText('Username').closest('form'));
 await vi.waitFor(()=>expect(calls.some(c=>c.options.method==='POST')).toBe(true));
 expect(JSON.parse(calls.find(c=>c.options.method==='POST').options.body)).toMatchObject({username:'bob',role:'EDITOR',departments:[]});
});
it('offers only Viewer and Editor to Department Administrators',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>[]})));
 render(<UsersAdmin departments={depts} role="DEPARTMENT_ADMIN" allowed/>);
 expect([...screen.getByLabelText('Role').options].map(o=>o.value)).toEqual(['VIEWER','EDITOR']);
});
it('shows nothing and sends no request without permission',()=>{
 const fetch=vi.fn();vi.stubGlobal('fetch',fetch);render(<UsersAdmin departments={depts} role="VIEWER" allowed={false}/>);
 expect(screen.queryByText('Create user')).not.toBeInTheDocument();expect(fetch).not.toHaveBeenCalled();
});
