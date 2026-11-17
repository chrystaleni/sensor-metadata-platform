// RFC 7946 positions are two-dimensional WGS84 [longitude, latitude].
const position = p => Array.isArray(p) && p.length === 2 && p.every(v => typeof v === 'number' && Number.isFinite(v)) && Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90;
const equal = (a,b) => a[0] === b[0] && a[1] === b[1];
const cross = (a,b,c) => (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
const onSegment = (a,b,p) => Math.abs(cross(a,b,p)) < 1e-12 && Math.min(a[0],b[0])<=p[0] && p[0]<=Math.max(a[0],b[0]) && Math.min(a[1],b[1])<=p[1] && p[1]<=Math.max(a[1],b[1]);
function intersects(a,b,c,d){
 const x=cross(a,b,c),y=cross(a,b,d),z=cross(c,d,a),w=cross(c,d,b);
 return (x*y<0 && z*w<0) || (Math.abs(x)<1e-12&&onSegment(a,b,c)) || (Math.abs(y)<1e-12&&onSegment(a,b,d)) || (Math.abs(z)<1e-12&&onSegment(c,d,a)) || (Math.abs(w)<1e-12&&onSegment(c,d,b));
}
function selfIntersection(r){
 const n=r.length-1;
 for(let i=0;i<n;i++)for(let j=i+1;j<n;j++){
  if(j===i+1||(i===0&&j===n-1))continue;
  if(intersects(r[i],r[i+1],r[j],r[j+1]))return true;
 }
 return false;
}
function area(r){let sum=0;for(let i=0;i<r.length-1;i++)sum+=r[i][0]*r[i+1][1]-r[i+1][0]*r[i][1];return Math.abs(sum)/2;}
function pointInRing(p,r){
 let inside=false;
 for(let i=0,j=r.length-2;i<r.length-1;j=i++){
  const a=r[i],b=r[j];
  if(onSegment(a,b,p))return false;
  if((a[1]>p[1])!==(b[1]>p[1]) && p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
 }
 return inside;
}
function ringsIntersect(a,b){for(let i=0;i<a.length-1;i++)for(let j=0;j<b.length-1;j++)if(intersects(a[i],a[i+1],b[j],b[j+1]))return true;return false;}
export function geometryError(g){
 if(!g || typeof g!=='object')return 'GeoJSON geometry is required.';
 if(Object.hasOwn(g,'crs')||Object.hasOwn(g,'srid'))return 'Explicit CRS/SRID is not supported; use WGS84 longitude/latitude.';
 const c=g.coordinates;
 if(!Array.isArray(c))return 'GeoJSON coordinates must be an array.';
 if(g.type==='Point')return position(c)?'':'Point requires valid 2D WGS84 longitude/latitude.';
 if(g.type==='LineString'){
  if(!c.every(position))return 'LineString requires valid 2D WGS84 positions.';
  if(c.length<2||new Set(c.map(JSON.stringify)).size<2)return 'A line requires at least two distinct points.';
  return '';
 }
 if(g.type==='Polygon'){
  if(!c.length)return 'Polygon requires at least one ring.';
  for(const r of c){
   if(!Array.isArray(r)||r.length<4||!r.every(position)||!equal(r[0],r[r.length-1])||new Set(r.slice(0,-1).map(JSON.stringify)).size<3)
    return 'A polygon requires closed rings with at least three distinct 2D vertices.';
   if(selfIntersection(r))return 'Self-intersecting polygons are not allowed.';
   if(area(r)<1e-12)return 'Polygon rings must have non-zero area.';
  }
  for(let i=1;i<c.length;i++){
   if(!pointInRing(c[i][0],c[0])||ringsIntersect(c[0],c[i]))return 'Polygon holes must lie inside the outer ring without intersecting it.';
   for(let j=1;j<i;j++)if(ringsIntersect(c[i],c[j])||pointInRing(c[i][0],c[j])||pointInRing(c[j][0],c[i]))return 'Polygon holes must not overlap.';
  }
  return '';
 }
 return 'Unsupported GeoJSON geometry type.';
}
