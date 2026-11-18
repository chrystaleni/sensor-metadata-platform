import { describe, expect, it, vi } from 'vitest';
import { ApiError, makeApiClient, normalizePage } from './apiClient';

describe('Django API transport', () => {
  it('uses cookies and CSRF for mutations', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, status: 201, json: async () => ({ id: 1 }) });
    const request = makeApiClient({ baseUrl: 'http://localhost:8000/api/', fetchImpl, csrf: () => 'token' });
    await request('/measurements/', { method: 'POST', data: { name: 'Meter' } });
    expect(fetchImpl).toHaveBeenCalledWith('http://localhost:8000/api/measurements/', expect.objectContaining({
      method: 'POST', credentials: 'include', body: JSON.stringify({ name: 'Meter' }),
      headers: expect.objectContaining({ 'X-CSRFToken': 'token' }),
    }));
  });
  it('forwards server filters and pagination', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ results: [], count: 0 }) });
    const request = makeApiClient({ baseUrl: '/api', fetchImpl });
    await request('/measurements/', { params: { search: 'abc', page: 2 } });
    const url = new URL(fetchImpl.mock.calls[0][0]);
    expect(url.searchParams.get('search')).toBe('abc');
    expect(url.searchParams.get('page')).toBe('2');
  });
  it('preserves validation errors', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: false, status: 400, json: async () => ({ name: ['Required'] }) });
    const request = makeApiClient({ baseUrl: '/api', fetchImpl });
    await expect(request('/measurements/')).rejects.toMatchObject({ status: 400, details: { name: ['Required'] } });
  });
  it('normalizes paginated and unpaginated lists', () => {
    expect(normalizePage([{ id: 1 }]).count).toBe(1);
    expect(normalizePage({ results: [], count: 10 }).count).toBe(10);
    expect(() => normalizePage({ items: [] })).toThrow(ApiError);
  });
});
