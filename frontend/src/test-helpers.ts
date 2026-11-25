import type { Me } from './app/useMe';

export const ownerMe: Me = {
  user: { id: 'u1', email: 'alex@example.com', name: 'Alex Rivera' },
  organization: { id: 'o1', name: 'Northwind Studio' },
  role: 'owner',
  csrf_token: 'csrf-123',
};

type Handler = { status?: number; body?: unknown };
export type Routes = Record<string, Handler | ((init: RequestInit) => Handler)>;

/** Replace global fetch with a router keyed by "METHOD /path" (path without /api/v1). */
export function mockFetch(routes: Routes) {
  const spy = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const path = String(input).replace(/^\/api\/v1/, '');
    const key = `${init.method ?? 'GET'} ${path}`;
    const route = routes[key];
    if (!route) {
      return new Response(JSON.stringify({ error: { code: 'not_mocked', message: key } }), {
        status: 404,
      });
    }
    const { status = 200, body } = typeof route === 'function' ? route(init) : route;
    if (status === 204) return new Response(null, { status });
    return new Response(JSON.stringify(body ?? {}), { status });
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

export const signedOut: Routes = {
  'GET /me': {
    status: 401,
    body: { error: { code: 'not_signed_in', message: 'You are not signed in', details: {} } },
  },
};
