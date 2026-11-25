import {render,screen,fireEvent,waitFor,cleanup,act} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import App from './App';

afterEach(()=>{cleanup();vi.unstubAllGlobals();window.location.hash='';});
it('ignores an older search response even when the transport fails to honor abort',async()=>{
 let resolveOld;
 vi.stubGlobal('fetch',vi.fn(async(raw)=>{
  const url=new URL(raw);let data;
  if(url.pathname.endsWith('/auth/session/'))data={authenticated:true};
  else if(url.pathname.endsWith('/auth/context/'))data={authenticated:true,role:'VIEWER',departments:[{id:7,name:'North',organisation:'Water',writable:false}],permissions:{manage_catalogs:false,manage_api_keys:false}};
  else if(url.searchParams.get('search')==='old')return new Promise(resolve=>{resolveOld=()=>resolve({ok:true,status:200,json:async()=>({count:1,results:[{id:1,name:'Stale result'}]})})});
  else if(url.searchParams.get('search')==='new')data={count:1,results:[{id:2,name:'Latest result'}]};
  else data={count:0,results:[]};
  return {ok:true,status:200,json:async()=>data};
 }));
 render(<App/>);await screen.findByRole('button',{name:'Profile menu'});
 fireEvent.click(screen.getByRole('link',{name:'Measurements',exact:true}));
 const search=await screen.findByLabelText('Search records');
 fireEvent.change(search,{target:{value:'old'}});await waitFor(()=>expect(resolveOld).toBeTypeOf('function'));
 fireEvent.change(search,{target:{value:'new'}});await screen.findByText('Latest result');
 await act(async()=>{resolveOld();});
 expect(screen.getByText('Latest result')).toBeInTheDocument();expect(screen.queryByText('Stale result')).not.toBeInTheDocument();
 expect(screen.queryByRole('button',{name:'+ Add'})).not.toBeInTheDocument();
});

function archiveApp(role){
 const calls=[];
 vi.stubGlobal('fetch',vi.fn(async(raw,init={})=>{
  const url=new URL(raw);calls.push({path:url.pathname,method:init.method||'GET',archived:url.searchParams.get('include_archived')});let data;
  if(url.pathname.endsWith('/auth/session/'))data={authenticated:true};
  else if(url.pathname.endsWith('/auth/context/'))data={authenticated:true,role,departments:[{id:7,name:'North',organisation:'Water',writable:role!=='VIEWER'}],permissions:{manage_catalogs:role==='SYSTEM_ADMIN',manage_api_keys:false}};
  else if(url.pathname.endsWith('/measurements/'))data={count:2,results:[{id:1,name:'Live flow',is_active:true},{id:2,name:'Old flow',is_active:false}].filter(r=>r.is_active||url.searchParams.get('include_archived'))};
  else if(url.pathname.endsWith('/restore/'))data={id:2,name:'Old flow',is_active:true};
  else if(init.method==='DELETE')return {ok:true,status:204,json:async()=>null};
  else data={count:0,results:[]};
  return {ok:true,status:200,json:async()=>data};
 }));
 return calls;
}
it('shows archived records faded with Restore and Delete to Department and System Administrators',async()=>{
 for(const role of ['DEPARTMENT_ADMIN','SYSTEM_ADMIN']){
  const calls=archiveApp(role);vi.stubGlobal('confirm',()=>true);
  render(<App/>);await screen.findByRole('button',{name:'Profile menu'});
  fireEvent.click(screen.getByRole('link',{name:'Measurements',exact:true}));
  const row=(await screen.findByText('Old flow')).closest('tr');
  expect(row).toHaveClass('all-archived');expect(row).toHaveTextContent('Archived');
  expect(row.querySelector('button:nth-of-type(2)')).toHaveTextContent('Restore');
  expect(screen.getByText('Live flow').closest('tr')).not.toHaveClass('all-archived');
  fireEvent.click(screen.getByRole('button',{name:'Restore'}));
  await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/measurements/2/restore/')&&c.method==='POST')).toBe(true));
  fireEvent.click(screen.getByRole('button',{name:'Delete'}));
  await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/measurements/2/purge/')&&c.method==='DELETE')).toBe(true));
  cleanup();window.location.hash='';
 }
});
it('hides archived records from Viewers and Editors',async()=>{
 for(const role of ['VIEWER','EDITOR']){
  const calls=archiveApp(role);
  render(<App/>);await screen.findByRole('button',{name:'Profile menu'});
  fireEvent.click(screen.getByRole('link',{name:'Measurements',exact:true}));
  await screen.findByText('Live flow');
  expect(screen.queryByText('Old flow')).not.toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Restore'})).not.toBeInTheDocument();
  expect(calls.filter(c=>c.path.endsWith('/measurements/')).every(c=>c.archived===null)).toBe(true);
  cleanup();window.location.hash='';
 }
});

function listsApp(role){
 const calls=[];
 vi.stubGlobal('fetch',vi.fn(async(raw,init={})=>{
  const url=new URL(raw);calls.push({path:url.pathname,method:init.method||'GET'});let data;
  const admin=['DEPARTMENT_ADMIN','SYSTEM_ADMIN'].includes(role);
  if(url.pathname.endsWith('/auth/session/'))data={authenticated:true};
  else if(url.pathname.endsWith('/auth/context/'))data={authenticated:true,role,departments:[{id:7,name:'North',organisation:'Water',writable:role!=='VIEWER'}],permissions:{manage_catalogs:admin,manage_api_keys:false}};
  else if(url.pathname.endsWith('/measurement-types/'))data={count:2,results:[{id:1,name:'Flow',is_active:true},{id:2,name:'Old type',is_active:false}].filter(r=>r.is_active||url.searchParams.get('include_archived'))};
  else if(init.method==='DELETE')return {ok:true,status:204,json:async()=>null};
  else data={count:0,results:[]};
  return {ok:true,status:200,json:async()=>data};
 }));
 return calls;
}
async function openLists(){render(<App/>);await screen.findByRole('button',{name:'Profile menu'});fireEvent.click(screen.getByRole('link',{name:'Controlled Lists',exact:true}));}
it('lets Department and System Administrators add, edit and delete shared list entries',async()=>{
 for(const role of ['DEPARTMENT_ADMIN','SYSTEM_ADMIN']){
  const calls=listsApp(role);vi.stubGlobal('confirm',()=>true);
  await openLists();
  const live=(await screen.findAllByText('Flow'))[0].closest('tr');
  expect(live).toHaveTextContent('Archive');
  expect(live).toHaveTextContent('Edit');expect(screen.getAllByRole('button',{name:/^\+ Add/}).length).toBeGreaterThan(0);
  const archived=(await screen.findAllByText('Old type'))[0].closest('tr');
  expect(archived).toHaveClass('all-archived');expect(archived).toHaveTextContent('Restore');expect(archived).toHaveTextContent('Delete');
  fireEvent.click(live.querySelector('button:last-of-type'));
  await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/measurement-types/1/')&&c.method==='DELETE')).toBe(true));
  cleanup();window.location.hash='';
 }
});
it('shows shared lists read-only to Viewers and Editors',async()=>{
 for(const role of ['VIEWER','EDITOR']){
  listsApp(role);
  await openLists();
  const live=(await screen.findAllByText('Flow'))[0].closest('tr');
  expect(live).not.toHaveTextContent('Archive');expect(live).not.toHaveTextContent('Edit');
  expect(screen.queryByText('Old type')).not.toBeInTheDocument();expect(screen.queryByRole('button',{name:/^\+ Add/})).not.toBeInTheDocument();
  cleanup();window.location.hash='';
 }
});

it('filters record tables by related records',async()=>{
 const listCalls=[];
 vi.stubGlobal('fetch',vi.fn(async(raw)=>{
  const url=new URL(raw);let data;
  if(url.pathname.endsWith('/auth/session/'))data={authenticated:true};
  else if(url.pathname.endsWith('/auth/context/'))data={authenticated:true,role:'VIEWER',departments:[{id:7,name:'North',organisation:'Water',writable:false}],permissions:{manage_catalogs:false,manage_api_keys:false}};
  else if(url.pathname.endsWith('/physical-device-types/'))data={count:2,results:[{id:11,name:'Logger'},{id:12,name:'Meter'}]};
  else if(url.pathname.endsWith('/physical-devices/')){if(url.searchParams.get('page_size')==='10')listCalls.push(url.searchParams.get('device_type'));data={count:0,results:[]};}
  else data={count:0,results:[]};
  return {ok:true,status:200,json:async()=>data};
 }));
 render(<App/>);await screen.findByRole('button',{name:'Profile menu'});
 fireEvent.click(screen.getByRole('link',{name:'Physical Devices',exact:true}));
 const filter=await screen.findByLabelText('Filter by device type');
 await waitFor(()=>expect([...filter.options].map(o=>o.textContent)).toEqual(['All','Logger','Meter']));
 fireEvent.change(filter,{target:{value:'12'}});
 await waitFor(()=>expect(listCalls).toContain('12'));
 fireEvent.click(screen.getByRole('button',{name:'Clear filters'}));
 await waitFor(()=>expect(listCalls.at(-1)).toBe(null));
});

it('keeps showing the name of an archived shared value that records still use',async()=>{
 const catalogCalls=[];
 vi.stubGlobal('fetch',vi.fn(async(raw)=>{
  const url=new URL(raw);let data;
  if(url.pathname.endsWith('/auth/session/'))data={authenticated:true};
  else if(url.pathname.endsWith('/auth/context/'))data={authenticated:true,role:'EDITOR',departments:[{id:7,name:'North',organisation:'Water',writable:true}],permissions:{manage_catalogs:false,manage_api_keys:false}};
  else if(url.pathname.endsWith('/physical-device-types/')){catalogCalls.push(url.searchParams.get('include_inactive'));data={count:2,results:[{id:11,name:'Logger',is_active:true},{id:12,name:'Old meter',is_active:false}]};}
  else if(url.pathname.endsWith('/physical-devices/'))data={count:1,results:[{id:1,name:'Pump RTU',department:7,device_type:12,is_active:true}]};
  else data={count:0,results:[]};
  return {ok:true,status:200,json:async()=>data};
 }));
 render(<App/>);await screen.findByRole('button',{name:'Profile menu'});
 fireEvent.click(screen.getByRole('link',{name:'Physical Devices',exact:true}));
 expect(await screen.findByText('Old meter (archived)')).toBeInTheDocument();
 expect(catalogCalls).toContain('true');
 fireEvent.click(screen.getByRole('button',{name:/^\+ Add/}));
 const typeSelect=screen.getByRole('dialog').querySelectorAll('select')[0];
 expect([...typeSelect.options].map(o=>o.textContent)).not.toContain('Old meter (#12)');
 expect([...typeSelect.options].map(o=>o.textContent)).toContain('Logger (#11)');
});
