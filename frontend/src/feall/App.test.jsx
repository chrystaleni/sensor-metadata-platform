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
