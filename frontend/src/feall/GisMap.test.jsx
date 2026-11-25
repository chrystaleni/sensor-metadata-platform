import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {describe,it,expect,vi} from 'vitest';
const mocks=vi.hoisted(()=>({fit:vi.fn(),view:vi.fn()}));
vi.mock('./greekBasemap',()=>({
 loadGreekMapStyle:async()=>({version:8,sources:{},layers:[]}),
 addGreekBasemap:vi.fn()
}));
vi.mock('./mapUtils',async importOriginal=>{
 const actual=await importOriginal();
 const bounds=name=>({name,isValid:()=>true,pad(){return this}});
 const group={layers:[],clearLayers(){this.layers=[]},getLayers(){return this.layers},getBounds:()=>bounds('all'),addTo(){return this}};
 const L={map:()=>({setView(...args){mocks.view(...args);return this},fitBounds:mocks.fit,attributionControl:{addAttribution:vi.fn()},invalidateSize(){},remove(){}}),tileLayer:()=>({addTo(){}}),featureGroup:()=>group,
  geoJSON:f=>({on(){return this},bindTooltip(){return this},addTo(g){g.layers.push(this);return this},getBounds:()=>bounds(f.properties.name)})};
 return {...actual,loadLeaflet:async()=>{window.L=L;return L}};
});
import GisMap from './GisMap';
describe('GIS resource identities',()=>{
 it('selects and zooms the correct resource when numeric IDs collide',async()=>{
  render(<GisMap records={{'physical-devices':[{id:1,name:'Device',latitude:35,longitude:33}], 'network-elements':[{id:1,name:'Network',geometryType:'Point',latitude:35,longitude:34}]}}/>);
  await waitFor(()=>expect(screen.queryByText('Loading interactive map…')).not.toBeInTheDocument());
  await waitFor(() => {
    expect(mocks.fit).toHaveBeenCalled();
    expect(mocks.fit.mock.calls.at(-1)[0].name).toBe('all');
  });
  fireEvent.click(screen.getByRole('button',{name:/Network Network Element/}));
  expect(screen.getByText('Selected metadata').parentElement.querySelector('dd').textContent).toBe('Network');
  expect(mocks.fit.mock.calls.at(-1)[0].name).toBe('Network');
  expect(screen.getByRole('button',{name:/Network Network Element/})).toHaveClass('selected');
  expect(screen.getByRole('button',{name:/Device Physical Device/})).not.toHaveClass('selected');
  fireEvent.click(screen.getByRole('button',{name:/Device Physical Device/}));
  expect(screen.getByText('Selected metadata').parentElement.querySelector('dd').textContent).toBe('Device');
  expect(mocks.fit.mock.calls.at(-1)[0].name).toBe('Device');
 });
 it('returns to the default view when the Department has nothing to map',async()=>{
  const devices=[{id:1,name:'Limassol device',latitude:34.68,longitude:33.03}];
  const {rerender}=render(<GisMap records={{'physical-devices':devices,'network-elements':[]}}/>);
  await waitFor(()=>expect(mocks.fit).toHaveBeenCalled());
  mocks.view.mockClear();
  rerender(<GisMap records={{'physical-devices':[],'network-elements':[]}}/>);
  await waitFor(()=>expect(mocks.fit).toHaveBeenLastCalledWith([[34.55,32.25],[35.72,34.62]],{animate:false}));
 });
 it('zooms to and selects the record passed from "Show on map"',async()=>{
  mocks.fit.mockClear();
  render(<GisMap focusKey="Network Element:1" records={{'physical-devices':[{id:1,name:'Device',latitude:35,longitude:33}],'network-elements':[{id:1,name:'Inlet',geometryType:'Point',latitude:35,longitude:34}]}}/>);
  await waitFor(()=>expect(mocks.fit).toHaveBeenCalled());
  expect(mocks.fit.mock.calls.find(c=>c[0]?.name)[0].name).toBe('Inlet');
  expect(screen.getByRole('button',{name:/Inlet Network Element/})).toHaveClass('selected');
  expect(screen.getByText('Selected metadata').parentElement.querySelector('dd').textContent).toBe('Inlet');
 });
 it('searches the map records by name, identifier or type',async()=>{
  render(<GisMap records={{'physical-devices':[{id:1,name:'Pump RTU',latitude:35,longitude:33,type:'Logger'}],'network-elements':[{id:2,name:'Inlet',geometryType:'Point',latitude:35,longitude:34,externalId:'ERP: NE-77'}]}}/>);
  const search=screen.getByLabelText('Search the map');
  fireEvent.change(search,{target:{value:'ne-77'}});
  expect(screen.getByRole('button',{name:/Inlet Network Element/})).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:/Pump RTU/})).not.toBeInTheDocument();
  fireEvent.change(search,{target:{value:'logger'}});
  expect(screen.getByRole('button',{name:/Pump RTU/})).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:/Inlet Network Element/})).not.toBeInTheDocument();
 });
});
