import { describe, expect, it } from 'vitest'

import en from '@/locales/en/terminal.json'
import fa from '@/locales/fa/terminal.json'
import { DOCKER_NAME, errorKey, LINUX_USER, newSessionId } from '@/modules/terminal/types'
import { NAVIGATION } from '@/navigation'

describe('terminal helpers', () => {
  it('creates session ids the WebSocket route accepts', () => {
    const ids = new Set(Array.from({ length: 50 }, () => newSessionId()))
    expect(ids.size).toBe(50)
    for (const id of ids) expect(id).toMatch(/^[A-Za-z0-9_-]{1,64}$/)
  })

  it('maps error codes to translated messages', () => {
    expect(errorKey('terminal.idle_timeout')).toBe('idle_timeout')
    expect(errorKey('agent.unavailable')).toBe('agent_unavailable')
    expect(errorKey('sudo')).toBe('sudo')
    expect(errorKey('something.else')).toBe('generic')
    for (const key of ['idle_timeout', 'invalid_start', 'refused', 'closed', 'agent_unavailable']) {
      expect(en.terminal.errors).toHaveProperty(key)
      expect(fa.terminal.errors).toHaveProperty(key)
    }
  })

  it('validates users and container names like the agent', () => {
    expect(LINUX_USER.test('root')).toBe(true)
    expect(LINUX_USER.test('deploy-1')).toBe(true)
    expect(LINUX_USER.test('Root')).toBe(false)
    expect(LINUX_USER.test('a;b')).toBe(false)
    expect(DOCKER_NAME.test('easydeploy-redis.1')).toBe(true)
    expect(DOCKER_NAME.test('bad name')).toBe(false)
    expect(DOCKER_NAME.test('-x')).toBe(false)
  })

  it('defers saved SSH hosts to a later phase', () => {
    const terminal = NAVIGATION.find((s) => s.key === 'terminal')
    const phases = Object.fromEntries(terminal?.pages.map((p) => [p.key, p.phase]) ?? [])
    expect(phases).toEqual({ local: 1, ssh_hosts: 2, container_exec: 1, snippets: 1 })
  })
})
