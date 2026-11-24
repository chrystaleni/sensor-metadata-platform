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

export function addGreekBasemap(map, style) {
  return maplibreGL({
    style,
    attributionControl: false
  }).addTo(map);
}
