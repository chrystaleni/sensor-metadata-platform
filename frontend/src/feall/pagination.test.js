import {describe, it, expect, vi} from 'vitest';
import {fetchAllPages, loadResources, latestRequest} from './pagination';

describe('complete and independent preload', () => {
  it('loads beyond the previous 1,000-record limit', async () => {
    const api = vi.fn(async (_path, {params}) => ({count:1101, results:Array.from({length:params.page === 12 ? 1 : 100}, (_, i) => ({id:(params.page-1)*100+i})), next:params.page < 12 ? 'next' : null}));
    expect(await fetchAllPages(api, '/measurements/')).toHaveLength(1101);
    expect(api).toHaveBeenCalledTimes(12);
  });
  it('keeps successful resources when one fails', async () => {
    const result = await loadResources(async path => {if(path === '/bad/') throw Error('denied'); return [{id:1}];}, ['good', 'bad']);
    expect(result[0].rows).toEqual([{id:1}]); expect(result[1].error.message).toBe('denied');
  });
  it('rejects stalled pagination instead of looping', async () => {
    await expect(fetchAllPages(async () => ({count:2, results:[], next:'next'}), '/rows/')).rejects.toThrow('Pagination stopped');
  });
  it('fails explicitly at the configured safety limit', async () => {
    await expect(fetchAllPages(async () => [{id:1}, {id:2}], '/rows/', {maxRecords:1})).rejects.toThrow('safety limit');
  });
  it('aborts superseded and unmounted requests', () => {
    const latest = latestRequest(); const old = latest.start(); const current = latest.start();
    expect(old.aborted).toBe(true); expect(current.aborted).toBe(false);
    latest.stop(); expect(current.aborted).toBe(true);
  });
  it('does not disguise aborts as partial resource errors', async () => {
    const controller = new AbortController(); controller.abort();
    await expect(loadResources(vi.fn(), ['devices'], {signal:controller.signal})).rejects.toMatchObject({name:'AbortError'});
  });
});
