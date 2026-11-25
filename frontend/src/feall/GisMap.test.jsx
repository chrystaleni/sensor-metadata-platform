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
  await waitFor(()=>expect(mocks.view).toHaveBeenCalledWith([35.14,33.39],10,{animate:false}));
 });
});
