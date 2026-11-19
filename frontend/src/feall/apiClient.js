// Django API transport. Endpoint paths and serializers must be confirmed with backend owner.
export class ApiError extends Error {
  constructor(message, status, details) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

export function makeApiClient({ baseUrl, fetchImpl = (...args) => globalThis.fetch(...args), csrf = () => '' }) {
  if (!baseUrl) throw new Error('Backend API base URL is not configured.');
  const root = baseUrl.replace(/\/+$/, '');
  return async function request(path, { method = 'GET', data, signal, params } = {}) {
    if (!/^\/[\w/-]*\/?$/.test(path)) throw new Error('Invalid API path.');
    const url = new URL(root + path, globalThis.location?.href);
    if (params) Object.entries(params).forEach(([key, value]) => {
      if (value !== '' && value !== null && value !== undefined) url.searchParams.set(key, String(value));
    });
    const headers = { Accept: 'application/json' };
    if (data !== undefined) headers['Content-Type'] = 'application/json';
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase()) && csrf()) headers['X-CSRFToken'] = csrf();
    let response;
    try {
      response = await fetchImpl(url.toString(), {
        method, headers, credentials: 'include', signal,
        ...(data === undefined ? {} : { body: JSON.stringify(data) }),
      });
    } catch (error) {
      if (error?.name === 'AbortError') throw error;
      throw new ApiError('Cannot connect to the backend service.', 0, null);
    }
    const payload = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      const message = typeof payload?.detail === 'string' ? payload.detail :
        typeof payload?.message === 'string' ? payload.message : `Request failed (HTTP ${response.status}).`;
      throw new ApiError(message, response.status, payload);
    }
    return payload;
  };
}

export function normalizePage(payload) {
  if (Array.isArray(payload)) return { results: payload, count: payload.length, next: null, previous: null };
  if (payload && Array.isArray(payload.results)) return {
    results: payload.results, count: payload.count ?? payload.results.length,
    next: payload.next ?? null, previous: payload.previous ?? null,
  };
  throw new ApiError('Unexpected list response from backend.', 200, payload);
}
