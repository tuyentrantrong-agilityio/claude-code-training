const BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, code: string, message: string, details: unknown = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

/** Build an ApiError from a status and a parsed (or missing) error body. */
export function apiErrorFrom(status: number, body: unknown): ApiError {
  let code = 'unknown_error';
  let message = `Request failed (${status})`;
  let details: unknown = {};
  const error = (body as { error?: { code?: string; message?: string; details?: unknown } } | null)
    ?.error;
  if (error) {
    code = error.code ?? code;
    message = error.message ?? message;
    details = error.details ?? details;
  }
  return new ApiError(status, code, message, details);
}

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
}

export async function api<T = void>(path: string, options: ApiOptions = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET' && csrfToken) headers['X-CSRF-Token'] = csrfToken;

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: 'include',
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // Body was not JSON; keep the defaults.
    }
    throw apiErrorFrom(response.status, body);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
