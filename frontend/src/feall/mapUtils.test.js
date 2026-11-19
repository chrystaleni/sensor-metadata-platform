import {describe,expect,it} from 'vitest';
import {buildMapFeatures,featureKey} from './mapUtils';
const row=(coordinates)=>({id:'n',name:'Test',geometryType:'LineString',geometry:JSON.stringify({type:'LineString',coordinates})});
describe('GIS map data safety',()=>{
 it('does not render malformed or degenerate lines',()=>{
  for(const coordinates of [[[33,35],[33,35]],[[[33,35],[34,36]]],[[33,35],[null,36]]]){
   const result=buildMapFeatures({'network-elements':[row(coordinates)]});
   expect(result.features).toHaveLength(0);
   expect(result.invalid).toHaveLength(1);
  }
 });
 it('renders a valid line',()=>{
  expect(buildMapFeatures({'network-elements':[row([[33,35],[34,36]])]}).features).toHaveLength(1);
 });
});

it('keeps geographic identities separate across resource tables',()=>{
 const {features}=buildMapFeatures({'physical-devices':[{id:1,name:'Device',latitude:35,longitude:33}], 'network-elements':[{id:1,name:'Network',geometryType:'Point',latitude:35,longitude:34}]});
 expect(features.map(featureKey)).toEqual(['Physical Device:1','Network Element:1']);
 expect(features.map(f=>f.properties.id)).toEqual([1,1]);
});
