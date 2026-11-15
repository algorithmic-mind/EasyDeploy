/** Shared terminal types; patterns mirror the agent's validators (`validators/names.py`). */

export interface TerminalTarget {
  mode: 'host' | 'container'
  user: string
  container: string | null
  shell_path: string
}

export type TerminalStatus = 'connecting' | 'open' | 'exited' | 'closed' | 'error'

export interface StatusDetail {
  code?: number | string
  fields?: string[]
}

export const SHELLS = ['/bin/bash', '/bin/sh', '/bin/ash', '/bin/zsh'] as const
export const LINUX_USER = /^[a-z_][a-z0-9_-]{0,31}$/
export const DOCKER_NAME = /^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$/

/** Session ids appear in the WebSocket path: `[A-Za-z0-9_-]{1,64}`. */
export function newSessionId(): string {
  return `t${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`
}

/** i18n key under `terminal.errors` for a close/error code. */
export function errorKey(code: number | string | undefined): string {
  if (code === 'sudo') return 'sudo'
  const key = String(code ?? '')
    .replace(/^terminal\./, '')
    .replace(/\./g, '_')
  const known = ['idle_timeout', 'invalid_start', 'refused', 'closed', 'agent_unavailable']
  return known.includes(key) ? key : 'generic'
}
