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
const people=[{id:1,username:'ann',role:'EDITOR',departments:[7],is_active:true},{id:9,username:'root',role:'SYSTEM_ADMIN',departments:[],is_active:true}];
it('offers Reset password only to System Administrators and never for themselves',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>people})));
 const {unmount}=render(<UsersAdmin departments={depts} role="SYSTEM_ADMIN" currentUser="root" allowed/>);
 expect(await screen.findByLabelText('Reset password for ann')).toBeInTheDocument();
 expect(screen.queryByLabelText('Reset password for root')).not.toBeInTheDocument();
 unmount();
 render(<UsersAdmin departments={depts} role="DEPARTMENT_ADMIN" currentUser="boss" allowed/>);
 await screen.findByText('ann');
 expect(screen.queryByLabelText(/Reset password for/)).not.toBeInTheDocument();
});
it('asks for the administrator password, shows the new password once and then removes it',async()=>{
 const calls=[];vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{calls.push({url,options});
  return {ok:true,status:200,json:async()=>options.method==='POST'?{id:1,username:'ann',password:'Fresh-Secret-123'}:people}}));
 render(<UsersAdmin departments={depts} role="SYSTEM_ADMIN" currentUser="root" allowed/>);
 fireEvent.click(await screen.findByLabelText('Reset password for ann'));
 const dialog=screen.getByRole('dialog',{name:'Reset password for ann'});
 expect(screen.queryByText('Fresh-Secret-123')).not.toBeInTheDocument();
 fireEvent.change(screen.getByLabelText('Your password'),{target:{value:'my-own-passphrase'}});
 fireEvent.submit(dialog.querySelector('form'));
 expect(await screen.findByText('Fresh-Secret-123')).toBeInTheDocument();
 const post=calls.find(c=>c.options.method==='POST');
 expect(post.url).toContain('/users/1/reset-password/');expect(JSON.parse(post.options.body)).toEqual({current_password:'my-own-passphrase'});
 fireEvent.click(screen.getByRole('button',{name:'Done'}));
 expect(screen.queryByText('Fresh-Secret-123')).not.toBeInTheDocument();
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
it('shows an error and no password when the administrator password is wrong',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url,options={})=>options.method==='POST'
  ?{ok:false,status:400,json:async()=>({current_password:['Your password is incorrect.']})}
  :{ok:true,status:200,json:async()=>people}));
 render(<UsersAdmin departments={depts} role="SYSTEM_ADMIN" currentUser="root" allowed/>);
 fireEvent.click(await screen.findByLabelText('Reset password for ann'));
 fireEvent.change(screen.getByLabelText('Your password'),{target:{value:'wrong-wrong-wrong'}});
 fireEvent.submit(screen.getByRole('dialog').querySelector('form'));
 expect(await screen.findByRole('alert')).toHaveTextContent(/incorrect/i);
 expect(screen.queryByLabelText('New password')).not.toBeInTheDocument();
});

function usersFetch(calls){return vi.fn(async(url,options={})=>{calls.push({url:String(url),method:options.method||'GET'});
 return {ok:true,status:options.method==='DELETE'?204:200,json:async()=>(options.method&&options.method!=='GET')?{}:[{id:5,username:'old',role:'EDITOR',departments:[7],is_active:false}]}})}
it('lets System Administrators reactivate or delete a deactivated user',async()=>{
 const calls=[];vi.stubGlobal('fetch',usersFetch(calls));vi.stubGlobal('confirm',()=>true);
 render(<UsersAdmin departments={depts} role="SYSTEM_ADMIN" allowed currentUser="sam"/>);
 fireEvent.click(await screen.findByRole('button',{name:'Reactivate old'}));
 await vi.waitFor(()=>expect(calls.some(c=>c.url.endsWith('/users/5/reactivate/')&&c.method==='POST')).toBe(true));
 fireEvent.click(await screen.findByRole('button',{name:'Delete old'}));
 await vi.waitFor(()=>expect(calls.some(c=>c.url.endsWith('/users/5/purge/')&&c.method==='DELETE')).toBe(true));
});
it('does not offer Reactivate or Delete to Department Administrators',async()=>{
 vi.stubGlobal('fetch',usersFetch([]));
 render(<UsersAdmin departments={depts} role="DEPARTMENT_ADMIN" allowed currentUser="sam"/>);
 await screen.findByText('old');
 expect(screen.queryByRole('button',{name:'Reactivate old'})).not.toBeInTheDocument();
 expect(screen.queryByRole('button',{name:'Delete old'})).not.toBeInTheDocument();
});

it('edits a user role and Departments',async()=>{
 const calls=[];vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{calls.push({url:String(url),method:options.method||'GET',body:options.body});
  return {ok:true,status:200,json:async()=>(options.method&&options.method!=='GET')?{}:[{id:3,username:'ann',role:'VIEWER',departments:[7],is_active:true},{id:4,username:'sam',role:'SYSTEM_ADMIN',departments:[],is_active:true}]}}));
 render(<UsersAdmin departments={[...depts,{id:8,name:'South',organisation:'Water'}]} role="SYSTEM_ADMIN" allowed currentUser="sam"/>);
 fireEvent.click(await screen.findByRole('button',{name:'Edit ann'}));
 expect(screen.queryByRole('button',{name:'Edit sam'})).not.toBeInTheDocument();
 const dialog=screen.getByRole('dialog',{name:'Edit ann'});
 fireEvent.change(dialog.querySelector('select'),{target:{value:'EDITOR'}});
 const multi=dialog.querySelectorAll('select')[1];[...multi.options].forEach(o=>{o.selected=true});fireEvent.change(multi);
 fireEvent.submit(dialog.querySelector('form'));
 await vi.waitFor(()=>expect(calls.some(c=>c.method==='PATCH')).toBe(true));
 const patch=calls.find(c=>c.method==='PATCH');
 expect(patch.url.endsWith('/users/3/')).toBe(true);
 expect(JSON.parse(patch.body)).toEqual({role:'EDITOR',departments:[7,8]});
});
it('offers Department Administrators only Viewer and Editor when editing',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>[{id:3,username:'ann',role:'VIEWER',departments:[7],is_active:true}]})));
 render(<UsersAdmin departments={depts} role="DEPARTMENT_ADMIN" allowed currentUser="dee"/>);
 fireEvent.click(await screen.findByRole('button',{name:'Edit ann'}));
 const options=[...screen.getByRole('dialog',{name:'Edit ann'}).querySelector('select').options].map(o=>o.value);
 expect(options).toEqual(['VIEWER','EDITOR']);
});
