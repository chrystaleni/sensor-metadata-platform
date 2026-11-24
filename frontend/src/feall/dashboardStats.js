// Pure helpers for the dashboard; everything is computed from records the API already returned.
const nameOf=(rows,id)=>rows?.find(r=>String(r.id)===String(id))?.name??`#${id}`;

export function breakdown(rows=[],field,lookup=[]){
 const counts=new Map();
 for(const row of rows){const key=row[field];if(key==null||key==='')continue;counts.set(key,(counts.get(key)||0)+1);}
 return [...counts].map(([id,count])=>({label:lookup.length?nameOf(lookup,id):String(id),count})).sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label));
}

const KIND_LABEL={Point:'Points',MultiPoint:'Points',LineString:'Lines',MultiLineString:'Lines',Polygon:'Polygons',MultiPolygon:'Polygons',GeometryCollection:'Mixed'};
export function geometryKinds(elements=[]){
 const counts=new Map();
 for(const e of elements){const label=e.geometry?KIND_LABEL[e.geometry.type]||e.geometry.type:'No geometry';counts.set(label,(counts.get(label)||0)+1);}
 return [...counts].map(([label,count])=>({label,count})).sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label));
}

export function recentActivity(lists,labels,limit=8){
 const rows=[];
 for(const [key,label] of Object.entries(labels))for(const r of lists[key]||[])rows.push({key,kind:label,id:r.id,name:r.name,at:r.updated_at||r.created_at,created:r.created_at===r.updated_at});
 return rows.filter(r=>r.at).sort((a,b)=>new Date(b.at)-new Date(a.at)).slice(0,limit);
}

export function completeness(lists){
 const m=lists.measurements||[],d=lists['physical-devices']||[],e=lists['network-elements']||[];
 return {
  measurements:m.length,withConfig:m.filter(r=>r.data_collection_config).length,
  withAccounts:m.filter(r=>r.customer_account||r.meter_account).length,
  mapped:d.filter(r=>r.location).length+e.filter(r=>r.geometry).length,
  mappable:d.length+e.length,
 };
}

export function relativeTime(iso,now=Date.now()){
 const s=Math.max(0,Math.round((now-new Date(iso))/1000));
 if(s<60)return 'just now';
 if(s<3600)return `${Math.floor(s/60)} min ago`;
 if(s<86400)return `${Math.floor(s/3600)} h ago`;
 return `${Math.floor(s/86400)} d ago`;
}
