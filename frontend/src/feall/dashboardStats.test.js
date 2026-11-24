import {it,expect} from 'vitest';
import {breakdown,geometryKinds,recentActivity,completeness,relativeTime} from './dashboardStats';
it('counts records by type name, largest first',()=>{
 const rows=[{t:1},{t:2},{t:2},{t:null}];
 expect(breakdown(rows,'t',[{id:1,name:'Flow'},{id:2,name:'Pressure'}])).toEqual([{label:'Pressure',count:2},{label:'Flow',count:1}]);
});
it('groups geometries into points, lines and polygons',()=>{
 expect(geometryKinds([{geometry:{type:'Point'}},{geometry:{type:'LineString'}},{geometry:{type:'Polygon'}},{geometry:{type:'Polygon'}},{geometry:null}]))
  .toEqual([{label:'Polygons',count:2},{label:'Lines',count:1},{label:'No geometry',count:1},{label:'Points',count:1}]);
});
it('lists the most recently updated records across types',()=>{
 const lists={measurements:[{id:1,name:'old',updated_at:'2026-01-01T00:00:00Z',created_at:'2026-01-01T00:00:00Z'}],'physical-devices':[{id:2,name:'new',updated_at:'2026-02-01T00:00:00Z',created_at:'2026-01-01T00:00:00Z'}]};
 const out=recentActivity(lists,{measurements:'Measurement','physical-devices':'Device'},1);
 expect(out).toHaveLength(1);expect(out[0]).toMatchObject({name:'new',kind:'Device',created:false});
});
it('measures completeness',()=>{
 expect(completeness({measurements:[{data_collection_config:{a:1},customer_account:'x'},{}],'physical-devices':[{location:{}}],'network-elements':[{geometry:null}]}))
  .toEqual({measurements:2,withConfig:1,withAccounts:1,mapped:1,mappable:2});
});
it('formats relative time',()=>{
 const now=Date.parse('2026-01-02T00:00:00Z');
 expect(relativeTime('2026-01-01T23:59:50Z',now)).toBe('just now');
 expect(relativeTime('2026-01-01T22:00:00Z',now)).toBe('2 h ago');
 expect(relativeTime('2025-12-30T00:00:00Z',now)).toBe('3 d ago');
});
