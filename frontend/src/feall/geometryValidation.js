// Validate GeoJSON geometry structure before passing it to Leaflet.
const isPosition = value => Array.isArray(value) && value.length >= 2 &&
  value.every(Number.isFinite) && Math.abs(value[0]) <= 180 && Math.abs(value[1]) <= 90;
const samePosition = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
const distinctPositions = positions => new Set(positions.map(p => JSON.stringify(p))).size;

export function geometryError(geometry) {
  if (!geometry || !Array.isArray(geometry.coordinates)) return 'GeoJSON coordinates must be an array.';
  const {type, coordinates} = geometry;
  if (type === 'Point') return isPosition(coordinates) ? '' : 'Point requires valid WGS84 longitude/latitude.';
  if (type === 'LineString') {
    if (!coordinates.every(isPosition)) return 'LineString requires valid WGS84 positions.';
    if (coordinates.length < 2 || distinctPositions(coordinates) < 2)
      return 'A line requires at least two distinct points.';
    return '';
  }
  if (type === 'Polygon') {
    if (!coordinates.length) return 'Polygon requires at least one ring.';
    for (const ring of coordinates) {
      if (!Array.isArray(ring) || !ring.every(isPosition) || ring.length < 4 ||
          !samePosition(ring[0], ring[ring.length - 1]) || distinctPositions(ring.slice(0, -1)) < 3)
        return 'A polygon requires closed rings with at least three distinct vertices.';
    }
    return '';
  }
  return 'Unsupported GeoJSON geometry type.';
}
