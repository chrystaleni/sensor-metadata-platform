import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import Settings from './Settings';
afterEach(()=>{cleanup();vi.unstubAllGlobals();localStorage.clear()});
const deps=[{id:7,name:'North',organisation:'Water',writable:true}];
const mk=role=>({role,user:{username:'sam'},departments:deps,permissions:{}});
const api=vi.fn(async()=>[]);
const show=role=>render(<Settings session={mk(role)} api={api} department="7" onDepartment={()=>{}} pickable={deps}/>);

it('shows every user their account, password and preferences only',()=>{
 show('VIEWER');
 expect(screen.getByText('My account')).toBeInTheDocument();
 expect(screen.getByRole('heading',{name:'Change password'})).toBeInTheDocument();
 expect(screen.getByText('Preferences')).toBeInTheDocument();
 expect(screen.queryByText('Department administration')).not.toBeInTheDocument();
 expect(screen.queryByText('Organisations and Departments')).not.toBeInTheDocument();
 expect(screen.queryByRole('heading',{name:'System'})).not.toBeInTheDocument();
});
it('adds Department administration for Department Administrators',()=>{
 show('DEPARTMENT_ADMIN');
 expect(screen.getByText('Department administration')).toBeInTheDocument();
 expect(screen.getByText('Manage users')).toBeInTheDocument();
 expect(screen.queryByText('Organisations and Departments')).not.toBeInTheDocument();
});
it('adds Organisations and Departments for System Administrators',()=>{
 show('SYSTEM_ADMIN');
 expect(screen.getByText('Organisations and Departments')).toBeInTheDocument();
 expect(screen.queryByRole('heading',{name:'System'})).not.toBeInTheDocument();
});
it('rejects mismatched new passwords without calling the server',()=>{
 const call=vi.fn();render(<Settings session={mk('EDITOR')} api={call} department="7" onDepartment={()=>{}} pickable={deps}/>);
 fireEvent.change(screen.getByLabelText('Current password'),{target:{value:'old-old-old-old'}});
 fireEvent.change(screen.getByLabelText('New password'),{target:{value:'new-long-passphrase'}});
 fireEvent.change(screen.getByLabelText('Confirm new password'),{target:{value:'different-passphrase'}});
 fireEvent.submit(screen.getByLabelText('New password').closest('form'));
 expect(screen.getByRole('alert')).toHaveTextContent('do not match');expect(call).not.toHaveBeenCalled();
});
it('remembers the default Department in this browser',()=>{
 const onDepartment=vi.fn();render(<Settings session={mk('VIEWER')} api={api} department="" onDepartment={onDepartment} pickable={deps}/>);
 fireEvent.change(screen.getByLabelText('Default Department'),{target:{value:'7'}});
 expect(localStorage.getItem('sensor.defaultDepartment')).toBe('7');expect(onDepartment).toHaveBeenCalledWith('7');
});

it('lets every role log out from Settings',()=>{
 for(const role of ['VIEWER','EDITOR','DEPARTMENT_ADMIN','SYSTEM_ADMIN']){
  const onLogout=vi.fn(async()=>{});
  render(<Settings session={mk(role)} api={api} department="7" onDepartment={()=>{}} pickable={deps} onLogout={onLogout}/>);
  fireEvent.click(screen.getByRole('button',{name:'Log out'}));
  expect(onLogout).toHaveBeenCalledTimes(1);
  cleanup();
 }
});

it('lets System Administrators delete Organisations and Departments, but never Platform',async()=>{
 const sent=[];vi.stubGlobal('confirm',()=>true);
 const sysApi=vi.fn(async(path,options={})=>{sent.push({path,method:options.method||'GET'});
  if(options.method)return {};
  if(path.startsWith('/organisations/'))return [{id:1,name:'Platform',code:'platform'},{id:2,name:'Spare',code:'spare'}];
  if(path.startsWith('/departments/'))return [{id:1,name:'Platform',organisation:1},{id:9,name:'Empty',organisation:2}];
  return [];});
 render(<Settings session={mk('SYSTEM_ADMIN')} api={sysApi} department="7" onDepartment={()=>{}} pickable={deps}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Delete Department Empty'}));
 await vi.waitFor(()=>expect(sent.some(c=>c.path==='/departments/9/'&&c.method==='DELETE')).toBe(true));
 fireEvent.click(screen.getByRole('button',{name:'Delete Organisation Spare'}));
 await vi.waitFor(()=>expect(sent.some(c=>c.path==='/organisations/2/'&&c.method==='DELETE')).toBe(true));
 expect(screen.queryByRole('button',{name:'Delete Organisation Platform'})).not.toBeInTheDocument();
 expect(screen.queryByRole('button',{name:'Delete Department Platform'})).not.toBeInTheDocument();
});
