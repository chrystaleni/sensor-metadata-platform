import { maplibreGL } from '@maplibre/maplibre-gl-leaflet';
import { setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import 'maplibre-gl/dist/maplibre-gl.css';

setWorkerUrl(workerUrl);

const STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty';

const countryNames = new Intl.DisplayNames(['el'], {
  type: 'region',
  fallback: 'none'
});

function countryExpression() {
  const expression = ['match', ['get', 'iso_a2']];

  for (const a of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') {
    for (const b of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') {
      const code = a + b;
      const name = countryNames.of(code);

      if (name) {
        expression.push(code, name);
      }
    }
  }

  expression.push('');
  return expression;
}

export async function loadGreekMapStyle() {
  const response = await fetch(STYLE_URL);

  if (!response.ok) {
    throw new Error('Unable to load map style');
  }

  const style = await response.json();

  for (const layer of style.layers) {
    if (layer.type !== 'symbol' || !layer.layout?.['text-field']) {
      continue;
    }

    if (layer.id.startsWith('label_country_')) {
      layer.layout['text-field'] = [
        'case',
        ['!=', ['coalesce', ['get', 'name:el'], ''], ''],
        ['get', 'name:el'],
        countryExpression()
      ];
    } else {
      layer.layout['text-field'] = [
        'coalesce',
        ['get', 'name:el'],
        ''
      ];
    }
  }

  return style;
}

const RASTER_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const VECTOR_TIMEOUT_MS = 10000;

export function supportsWebGL() {
  try {
    const canvas = document.createElement('canvas');
    return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'));
  } catch {
    return false;
  }
}

// Plain OpenStreetMap image tiles: no WebGL, no web worker, no style file.
export function addRasterBasemap(map, L) {
  return L.tileLayer(RASTER_URL, { maxZoom: 19, attribution: '© OpenStreetMap contributors' }).addTo(map);
}

// The Greek vector basemap needs WebGL, a module web worker and tiles.openfreemap.org. When any of these is
// missing (graphics acceleration off, older browser, blocked network) it only paints its beige background,
// so fall back to plain OpenStreetMap tiles instead of leaving an empty map.
export function addGreekBasemap(map, style, L = globalThis.L, { timeout = VECTOR_TIMEOUT_MS } = {}) {
  if (!style || !supportsWebGL()) {
    return addRasterBasemap(map, L);
  }
  let layer;
  try {
    layer = maplibreGL({
      style,
      attributionControl: false
    }).addTo(map);
  } catch {
    return addRasterBasemap(map, L);
  }
  let fellBack = false;
  const fallBack = () => {
    if (fellBack) return;
    fellBack = true;
    clearTimeout(timer);
    try { map.removeLayer(layer); } catch { /* already gone */ }
    addRasterBasemap(map, L);
  };
  const vector = layer.getMaplibreMap?.();
  let loaded = false;
  vector?.on?.('error', () => { if (!loaded) fallBack(); });
  vector?.on?.('idle', () => {
    loaded = vector.areTilesLoaded?.() !== false && vector.loaded?.() !== false;
    if (loaded) clearTimeout(timer);
  });
  const timer = setTimeout(() => { if (!loaded) fallBack(); }, timeout);

  // Keep the map matched to its container, not only to the browser window
  // (for example when the layout around the map changes).
  const container = map.getContainer();

  if (typeof ResizeObserver !== 'undefined' && container) {
    const observer = new ResizeObserver(() => {
      if (map._loaded) {
        map.invalidateSize();
      }
    });

    observer.observe(container);
    map.on('unload', () => observer.disconnect());
  }

  return layer;
}
