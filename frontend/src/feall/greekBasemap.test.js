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

describe('addGreekBasemap',()=>{
  it('keeps the map sized to its container',async()=>{
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

    addGreekBasemap(map,{});
    expect(observe).toHaveBeenCalled();

    callback();
    expect(map.invalidateSize).toHaveBeenCalled();

    handlers.unload();
    expect(disconnect).toHaveBeenCalled();
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
