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

// Label-free fallback tiles. Standard OpenStreetMap tiles show local names, which are Turkish in the
// north of Cyprus; the platform's map must show Greek names only (the vector map) or no names at all.
const RASTER_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}';
const VECTOR_TIMEOUT_MS = 10000;

export function supportsWebGL() {
  try {
    const canvas = document.createElement('canvas');
    return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'));
  } catch {
    return false;
  }
}

// Plain image tiles without place names: no WebGL, no web worker, no style file.
export function addRasterBasemap(map, L) {
  // Tile servers may refuse requests without a Referer. The app sends Referrer-Policy: same-origin,
  // so this layer asks the browser to send its origin (never the page path) to the tile server.
  return L.tileLayer(RASTER_URL, {
    maxZoom: 19,
    maxNativeZoom: 16,
    attribution: 'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors',
    referrerPolicy: 'strict-origin-when-cross-origin'
  }).addTo(map);
}

// The Greek vector basemap needs WebGL, a module web worker and tiles.openfreemap.org. When any of these is
// missing (graphics acceleration off, older browser, blocked network) it only paints its beige background,
// so fall back to plain, label-free tiles instead of leaving an empty map.
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
