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
      // Greek, then English, never the local name (which is Turkish in the occupied area).
      // Only the explicit name:en tag: the tiles' name_en falls back to the local name.
      layer.layout['text-field'] = [
        'coalesce',
        ['get', 'name:el'],
        ['get', 'name:en'],
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
  return rasterBasemap(L).addTo(map);
}

export function rasterBasemap(L) {
  // Tile servers may refuse requests without a Referer. The app sends Referrer-Policy: same-origin,
  // so this layer asks the browser to send its origin (never the page path) to the tile server.
  return L.tileLayer(RASTER_URL, {
    maxZoom: 19,
    maxNativeZoom: 16,
    attribution: 'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors',
    referrerPolicy: 'strict-origin-when-cross-origin'
  });
}

// The Greek vector basemap needs WebGL, a module web worker and tiles.openfreemap.org. When any of these is
// missing (graphics acceleration off, older browser, blocked network) it only paints its beige background,
// so fall back to plain, label-free tiles instead of leaving an empty map.
export function addGreekBasemap(map, style, L = globalThis.L, { timeout = VECTOR_TIMEOUT_MS, onFallback } = {}) {
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
    const raster = addRasterBasemap(map, L);
    onFallback?.(layer, raster);
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

// Orthophoto of the Department of Lands and Surveys (Republic of Cyprus): aerial imagery, no place names.
const DLS_ORTHO_2019 = 'https://eservices.dls.moi.gov.cy/arcgis/services/BASEMAPS/Orthoimagery_2019_WebMercator/MapServer/WMSServer';
export const BASEMAP_NAMES = { map: 'Χάρτης', plain: 'Απλός (χωρίς ονόματα)', ortho: 'Ορθοφωτοχάρτης 2019 (ΤΚΧ)' };

export function orthophotoBasemap(L) {
  return L.tileLayer.wms(DLS_ORTHO_2019, {
    layers: '0',
    format: 'image/png',
    transparent: false,
    maxZoom: 19,
    attribution: '© Department of Lands and Surveys'
  });
}

// The GIS Map's basemap switcher (top right), metric scale and fullscreen button. The "Χάρτης" entry is the
// Greek vector map, or the label-free tiles when the vector map cannot draw.
export function addMapControls(map, style, L = globalThis.L, options = {}) {
  const control = L.control.layers({}, {}, { position: 'topright', collapsed: true });
  const main = addGreekBasemap(map, style, L, {
    ...options,
    onFallback: (vector, raster) => {
      control.removeLayer(vector);
      control.addBaseLayer(raster, BASEMAP_NAMES.map);
    }
  });
  control.addBaseLayer(main, BASEMAP_NAMES.map);
  control.addBaseLayer(rasterBasemap(L), BASEMAP_NAMES.plain);
  control.addBaseLayer(orthophotoBasemap(L), BASEMAP_NAMES.ortho);
  control.addTo(map);
  L.control.scale({ position: 'bottomleft', imperial: false }).addTo(map);
  addFullscreenControl(map, L);
  return control;
}

function addFullscreenControl(map, L) {
  const container = map.getContainer();
  if (!container?.requestFullscreen) return;
  const Fullscreen = L.Control.extend({
    options: { position: 'topleft' },
    onAdd() {
      const button = L.DomUtil.create('button', 'leaflet-bar gis-fullscreen');
      button.type = 'button';
      button.title = 'Πλήρης οθόνη';
      button.setAttribute('aria-label', 'Πλήρης οθόνη');
      button.textContent = '⛶';
      L.DomEvent.disableClickPropagation(button);
      L.DomEvent.on(button, 'click', () => {
        if (document.fullscreenElement) document.exitFullscreen?.();
        else container.requestFullscreen().catch(() => {});
      });
      return button;
    }
  });
  new Fullscreen().addTo(map);
  const resize = () => map.invalidateSize();
  document.addEventListener('fullscreenchange', resize);
  map.on('unload', () => document.removeEventListener('fullscreenchange', resize));
}
