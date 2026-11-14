/**
 * Thin typed fetch wrapper: JSON, CSRF header, request IDs and the API error envelope (§10.1).
 * Endpoint functions live in `client.ts` and use the types generated from OpenAPI (`schema.d.ts`).
 */

export interface ErrorBody {
  code: string
  message: string
  details: Record<string, unknown>
  request_id: string | null
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>
  readonly requestId: string | null

  constructor(status: number, body: ErrorBody) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.details = body.details ?? {}
    this.requestId = body.request_id ?? null
  }

  /** Field errors from a validation envelope: `{field: ["msg", …]}`. */
  fieldErrors(): Record<string, string[]> {
    const out: Record<string, string[]> = {}
    for (const [field, value] of Object.entries(this.details)) {
      if (Array.isArray(value)) out[field] = value.map(String)
      else if (typeof value === 'string') out[field] = [value]
    }
    return out
  }

  get isAuthError(): boolean {
    return this.status === 401 || this.code === 'auth.not_authenticated'
  }
}

const CSRF_COOKIE = 'ed_csrftoken'
const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

let currentLanguage = 'en'
let unauthorizedHandler: (() => void) | null = null

export function setRequestLanguage(lang: string): void {
  currentLanguage = lang
}

/** Called when any request answers 401/403 not-authenticated (session expired). */
export function onUnauthorized(handler: () => void): void {
  unauthorizedHandler = handler
}

export function readCookie(name: string): string | null {
  for (const part of document.cookie.split(';')) {
    const [key, ...rest] = part.trim().split('=')
    if (key === name) return decodeURIComponent(rest.join('='))
  }
  return null
}

export type Query = Record<string, string | number | boolean | null | undefined>

function withQuery(path: string, query?: Query): string {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

export async function request<T>(
  method: string,
  path: string,
  options: { body?: unknown; query?: Query; signal?: AbortSignal } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Accept-Language': currentLanguage,
  }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (UNSAFE.has(method)) {
    const csrf = readCookie(CSRF_COOKIE)
    if (csrf) headers['X-CSRFToken'] = csrf
  }
  const response = await fetch(withQuery(path, options.query), {
    method,
    headers,
    credentials: 'same-origin',
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  })
  if (response.status === 204) return undefined as T
  const text = await response.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }
  if (!response.ok) {
    const envelope = (data as { error?: ErrorBody } | null)?.error
    const error = new ApiError(
      response.status,
      envelope ?? {
        code: response.status === 404 ? 'not_found' : 'http_error',
        message: response.statusText || `HTTP ${response.status}`,
        details: {},
        request_id: response.headers.get('X-Request-ID'),
      },
    )
    if (
      (response.status === 401 || error.code === 'auth.not_authenticated') &&
      unauthorizedHandler
    ) {
      unauthorizedHandler()
    }
    throw error
  }
  return data as T
}

export const http = {
  get: <T>(path: string, query?: Query) => request<T>('GET', path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, { body }),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, { body }),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, { body }),
  delete: <T>(path: string) => request<T>('DELETE', path),
}
