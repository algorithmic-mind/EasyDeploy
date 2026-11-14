/**
 * WebSocket helper with automatic reconnect and exponential backoff (§13.2).
 * Close codes 4401/4403/4404 are final (auth, origin, not found) and stop reconnecting.
 */

const FINAL_CODES = new Set([1000, 4401, 4403, 4404])

export interface SocketOptions<T> {
  onMessage: (data: T) => void
  onStatus?: (status: 'connecting' | 'open' | 'closed') => void
  maxDelayMs?: number
}

export interface SocketHandle {
  close: () => void
}

export function wsUrl(path: string): string {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${window.location.host}${path}`
}

export function openSocket<T>(path: string, options: SocketOptions<T>): SocketHandle {
  let socket: WebSocket | null = null
  let attempts = 0
  let stopped = false
  let timer: ReturnType<typeof setTimeout> | null = null
  const maxDelay = options.maxDelayMs ?? 15000

  const connect = () => {
    if (stopped) return
    options.onStatus?.('connecting')
    socket = new WebSocket(wsUrl(path))
    socket.onopen = () => {
      attempts = 0
      options.onStatus?.('open')
    }
    socket.onmessage = (event: MessageEvent<string>) => {
      try {
        options.onMessage(JSON.parse(event.data) as T)
      } catch {
        // ignore malformed frames
      }
    }
    socket.onclose = (event: CloseEvent) => {
      options.onStatus?.('closed')
      if (stopped || FINAL_CODES.has(event.code)) return
      const delay = Math.min(maxDelay, 500 * 2 ** attempts) + Math.random() * 250
      attempts += 1
      timer = setTimeout(connect, delay)
    }
  }

  connect()
  return {
    close: () => {
      stopped = true
      if (timer) clearTimeout(timer)
      socket?.close(1000)
    },
  }
}
