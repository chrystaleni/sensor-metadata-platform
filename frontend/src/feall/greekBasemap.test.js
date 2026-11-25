import {describe,it,expect,vi,afterEach} from 'vitest';
import {readFileSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

vi.mock('@maplibre/maplibre-gl-leaflet',()=>({
  maplibreGL:vi.fn()
}));

vi.mock('maplibre-gl',()=>({
  setWorkerUrl:vi.fn()
}));

import {loadGreekMapStyle,addGreekBasemap} from './greekBasemap';

afterEach(()=>vi.unstubAllGlobals());

function mockStyle(layers){
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({
    ok:true,
    json:async()=>({version:8,layers})
  }));
}

describe('Greek basemap',()=>{

  it('uses Greek names without foreign language fallback',async()=>{
    mockStyle([{
      id:'label_city',
      type:'symbol',
      layout:{'text-field':['get','name']}
    }]);

    const style=await loadGreekMapStyle();

    expect(style.layers[0].layout['text-field'])
      .toEqual(['coalesce',['get','name:el'],'']);
  });

  it('provides Greek country names using ISO codes',async()=>{
    mockStyle([{
      id:'label_country_1',
      type:'symbol',
      layout:{'text-field':['get','name']}
    }]);

    const style=await loadGreekMapStyle();
    const expression=style.layers[0].layout['text-field'];
    const fallback=expression[3];

    expect(fallback[fallback.indexOf('CY')+1]).toBe('Κύπρος');
    expect(fallback[fallback.indexOf('GR')+1]).toBe('Ελλάδα');
    expect(fallback[fallback.indexOf('FR')+1]).toBe('Γαλλία');
  });

  it('preserves non-label layers',async()=>{
    const road={
      id:'road',
      type:'line',
      paint:{'line-color':'#ffffff'}
    };

    mockStyle([road]);

    const style=await loadGreekMapStyle();
    expect(style.layers[0]).toEqual(road);
  });

  it('handles unavailable map styles',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue({
      ok:false
    }));

    await expect(loadGreekMapStyle())
      .rejects.toThrow('Unable to load map style');
  });
});

const withWebGL=on=>vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockImplementation(type=>on&&String(type).startsWith('webgl')?{}:null);
const leaflet=()=>{const raster={addTo:vi.fn(function(){return this})};return {raster,L:{tileLayer:vi.fn(()=>raster)}};};
function vectorLayer(){const events={};const vector={on:vi.fn((name,fn)=>{events[name]=fn}),areTilesLoaded:()=>true,loaded:()=>true};
 const layer={getMaplibreMap:()=>vector};layer.addTo=()=>layer;return {layer,events};}
function plainMap(){return {getContainer:()=>({}),invalidateSize:vi.fn(),on:vi.fn(),removeLayer:vi.fn()};}

describe('addGreekBasemap',()=>{
  afterEach(()=>{vi.restoreAllMocks();vi.useRealTimers();});
  it('keeps the map sized to its container',async()=>{
    withWebGL(true);
    const {maplibreGL}=await import('@maplibre/maplibre-gl-leaflet');
    maplibreGL.mockReturnValue({addTo:()=>({})});
    let callback;
    const observe=vi.fn();
    const disconnect=vi.fn();
    vi.stubGlobal('ResizeObserver',class{constructor(cb){callback=cb}observe=observe;disconnect=disconnect});
    const handlers={};
    const map={
      _loaded:true,
      getContainer:()=>({}),
      invalidateSize:vi.fn(),
      on:vi.fn((name,fn)=>{handlers[name]=fn})
    };

    addGreekBasemap(map,{},leaflet().L);
    expect(observe).toHaveBeenCalled();

    callback();
    expect(map.invalidateSize).toHaveBeenCalled();

    handlers.unload();
    expect(disconnect).toHaveBeenCalled();
  });

  it('uses plain OpenStreetMap tiles when the browser has no WebGL',async()=>{
    const {maplibreGL}=await import('@maplibre/maplibre-gl-leaflet');maplibreGL.mockClear();
    withWebGL(false);const {L,raster}=leaflet();const map=plainMap();
    addGreekBasemap(map,{},L);
    expect(maplibreGL).not.toHaveBeenCalled();
    expect(L.tileLayer.mock.calls[0][0]).toBe('https://tile.openstreetmap.org/{z}/{x}/{y}.png');
    // Without a Referer, OpenStreetMap answers "Access blocked" (tile usage policy).
    expect(L.tileLayer.mock.calls[0][1].referrerPolicy).toBe('strict-origin-when-cross-origin');
    expect(raster.addTo).toHaveBeenCalledWith(map);
  });

  it('uses plain OpenStreetMap tiles when the map style could not be loaded',()=>{
    withWebGL(true);const {L}=leaflet();
    addGreekBasemap(plainMap(),null,L);
    expect(L.tileLayer).toHaveBeenCalled();
  });

  it('switches to plain tiles when the vector map reports an error before loading',async()=>{
    const {maplibreGL}=await import('@maplibre/maplibre-gl-leaflet');
    withWebGL(true);const {layer,events}=vectorLayer();maplibreGL.mockReturnValue(layer);
    const {L}=leaflet();const map=plainMap();
    addGreekBasemap(map,{},L);
    expect(L.tileLayer).not.toHaveBeenCalled();
    events.error(new Error('tiles blocked'));
    expect(map.removeLayer).toHaveBeenCalledWith(layer);
    expect(L.tileLayer).toHaveBeenCalledTimes(1);
  });

  it('switches to plain tiles when the vector map never finishes loading',async()=>{
    vi.useFakeTimers();
    const {maplibreGL}=await import('@maplibre/maplibre-gl-leaflet');
    withWebGL(true);const {layer}=vectorLayer();maplibreGL.mockReturnValue(layer);
    const {L}=leaflet();
    addGreekBasemap(plainMap(),{},L,{timeout:1000});
    vi.advanceTimersByTime(1000);
    expect(L.tileLayer).toHaveBeenCalledTimes(1);
  });

  it('keeps the vector map once it has loaded',async()=>{
    vi.useFakeTimers();
    const {maplibreGL}=await import('@maplibre/maplibre-gl-leaflet');
    withWebGL(true);const {layer,events}=vectorLayer();maplibreGL.mockReturnValue(layer);
    const {L}=leaflet();const map=plainMap();
    addGreekBasemap(map,{},L,{timeout:1000});
    events.idle();vi.advanceTimersByTime(5000);events.error(new Error('one tile failed later'));
    expect(L.tileLayer).not.toHaveBeenCalled();
    expect(map.removeLayer).not.toHaveBeenCalled();
  });
});

describe('map worker deployment',()=>{
  // MapLibre starts its worker from an ES module (.mjs). Browsers refuse a
  // module that is not served as JavaScript and nginx has no default type
  // for .mjs, which left the basemap blank in the Docker deployment.
  it('serves .mjs files as JavaScript in the nginx configuration',()=>{
    const here=dirname(fileURLToPath(import.meta.url));
    const config=readFileSync(resolve(here,'../../../docker/nginx.conf'),'utf8');

    expect(config).toMatch(/location\s+~\*?\s+\\\.mjs\$\s*\{[^}]*default_type\s+(text|application)\/javascript\s*;/);
  });
});
