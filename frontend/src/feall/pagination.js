import {normalizePage} from './apiClient';

// A visible failure is preferable to silently presenting a truncated data set.
export async function fetchAllPages(api, path, {params = {}, signal, maxRecords = 100000} = {}) {
  const rows = [];
  for (let page = 1; ; page++) {
    signal?.throwIfAborted();
    const result = normalizePage(await api(path, {params: {...params, page, page_size: 100}, signal}));
    rows.push(...result.results);
    if (rows.length > maxRecords) throw Error(`Dataset exceeds the ${maxRecords.toLocaleString('en-US')}-record safety limit; narrow the Department scope.`);
    if (rows.length >= result.count && !result.next) return rows;
    if (!result.results.length) throw Error('Pagination stopped before all records were returned. Retry the request.');
    if (page >= Math.ceil(maxRecords / 100)) throw Error('Pagination safety limit reached; narrow the Department scope.');
  }
}

export async function loadResources(api, keys, options) {
  return Promise.all(keys.map(async key => {
    try { return {key, rows: await fetchAllPages(api, `/${key}/`, options)}; }
    catch (error) { if (error.name === 'AbortError') throw error; return {key, rows: [], error}; }
  }));
}

export function latestRequest() {
  let controller;
  return {
    start() { controller?.abort(); controller = new AbortController(); return controller.signal; },
    stop() { controller?.abort(); },
  };
}
