import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, http, onUnauthorized, setRequestLanguage } from '@/api/http'

function mockFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  const fn = vi
    .fn()
    .mockResolvedValue(
      new Response(body === undefined ? null : JSON.stringify(body), { status, headers }),
    )
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.cookie = 'ed_csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

describe('http', () => {
  it('sends JSON, CSRF token and language on unsafe requests', async () => {
    document.cookie = 'ed_csrftoken=abc123'
    setRequestLanguage('fa')
    const fetch = mockFetch(200, { ok: true })
    await http.post('/api/v1/x', { a: 1 })
    const [url, init] = fetch.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/v1/x')
    const headers = init.headers as Record<string, string>
    expect(headers['X-CSRFToken']).toBe('abc123')
    expect(headers['Accept-Language']).toBe('fa')
    expect(init.body).toBe('{"a":1}')
  })

  it('omits empty query params', async () => {
    const fetch = mockFetch(200, {})
    await http.get('/api/v1/tasks', { status: 'running', search: '', page: undefined })
    expect(fetch.mock.calls[0]?.[0]).toBe('/api/v1/tasks?status=running')
  })

  it('maps the error envelope to ApiError with field errors', async () => {
    mockFetch(400, {
      error: {
        code: 'validation_error',
        message: 'Some fields are invalid.',
        details: { password: ['Too short.'] },
        request_id: 'r1',
      },
    })
    const error = await http.post('/api/v1/auth/login', {}).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    const apiError = error as ApiError
    expect(apiError.code).toBe('validation_error')
    expect(apiError.fieldErrors()).toEqual({ password: ['Too short.'] })
    expect(apiError.requestId).toBe('r1')
  })

  it('calls the unauthorized handler on 401', async () => {
    const handler = vi.fn()
    onUnauthorized(handler)
    mockFetch(401, {
      error: { code: 'auth.not_authenticated', message: 'x', details: {}, request_id: null },
    })
    await http.get('/api/v1/auth/me').catch(() => undefined)
    expect(handler).toHaveBeenCalledOnce()
  })

  it('returns undefined for 204', async () => {
    mockFetch(204, undefined)
    await expect(http.post('/api/v1/auth/logout')).resolves.toBeUndefined()
  })
})
