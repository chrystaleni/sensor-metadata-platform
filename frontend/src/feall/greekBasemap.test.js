import {describe,it,expect,vi,afterEach} from 'vitest';

vi.mock('@maplibre/maplibre-gl-leaflet',()=>({
  maplibreGL:vi.fn()
}));

vi.mock('maplibre-gl',()=>({
  setWorkerUrl:vi.fn()
}));

import {loadGreekMapStyle} from './greekBasemap';

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
