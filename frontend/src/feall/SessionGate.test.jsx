import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {afterEach,describe,it,expect,vi} from 'vitest';
import {SessionGate} from './SessionGate';

const context={authenticated:true,role:'EDITOR',departments:[{id:7,name:'North',organisation:'Customer',writable:true}],permissions:{write_metadata:true,manage_catalogs:false}};
function Workspace({session,onLogout,onSessionCheck}){return <><p>{session.departments[0].name}</p><button onClick={onLogout}>Log out</button><button onClick={onSessionCheck}>Check session</button></>;}
function setup(authenticated=false){
 const calls=[];
 const mock=vi.fn(async(url,options={})=>{
  const path=new URL(url).pathname;calls.push({path,options});
  if(path.endsWith('/login/'))authenticated=true;
  if(path.endsWith('/logout/'))authenticated=false;
  return {ok:true,status:200,json:async()=>path.endsWith('/context/')?context:{authenticated}};
 });
 vi.stubGlobal('fetch',mock);
 return {calls,expire:()=>{authenticated=false;}};
}
afterEach(()=>{cleanup();vi.unstubAllGlobals();document.cookie='csrftoken=; max-age=0';});
describe('session UI',()=>{
 it('restores an existing session without asking for credentials',async()=>{
  setup(true);render(<SessionGate component={Workspace}/>);
  expect(await screen.findByText('North')).toBeInTheDocument();
  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
 });
 it('bootstraps CSRF, logs in with cookies, and logs out',async()=>{
  const {calls}=setup();document.cookie='csrftoken=test-token';render(<SessionGate component={Workspace}/>);
  fireEvent.change(await screen.findByLabelText('Username'),{target:{value:'editor'}});
  fireEvent.change(screen.getByLabelText('Password'),{target:{value:'test-only'}});
  fireEvent.click(screen.getByRole('button',{name:'Sign in'}));
  await screen.findByText('North');
  const login=calls.find(c=>c.path.endsWith('/login/'));
  expect(calls.findIndex(c=>c.path.endsWith('/csrf/'))).toBeLessThan(calls.indexOf(login));
  expect(login.options.credentials).toBe('include');
  expect(login.options.headers['X-CSRFToken']).toBe('test-token');
  expect(JSON.parse(login.options.body)).toEqual({username:'editor',password:'test-only'});
  fireEvent.click(screen.getByText('Log out'));
  expect(await screen.findByLabelText('Password')).toBeInTheDocument();
 });
 it('unmounts protected data when the server reports expiration',async()=>{
  const {expire}=setup(true);render(<SessionGate component={Workspace}/>);await screen.findByText('North');
  expire();fireEvent.click(screen.getByText('Check session'));
  await screen.findByLabelText('Password');expect(screen.queryByText('North')).not.toBeInTheDocument();
 });
 it('shows server errors and never opens the protected workspace on failed login',async()=>{
  setup();render(<SessionGate component={Workspace}/>);await screen.findByLabelText('Username');
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:429,json:async()=>({detail:'Try again later.'})})));
  fireEvent.change(screen.getByLabelText('Username'),{target:{value:'a'}});
  fireEvent.change(screen.getByLabelText('Password'),{target:{value:'b'}});
  fireEvent.submit(screen.getByLabelText('Username').closest('form'));
  await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('Try again later.'));
  expect(screen.queryByText('North')).not.toBeInTheDocument();
 });
});
