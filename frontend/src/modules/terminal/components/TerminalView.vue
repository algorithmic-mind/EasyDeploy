<script setup lang="ts">
/**
 * One terminal tab: xterm.js bound to `/ws/terminal/<session>/` (§9.10).
 * Output arrives as binary frames; `started` / `exit` / `error` as JSON text frames.
 */
import { FitAddon } from '@xterm/addon-fit'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { wsUrl } from '@/api/ws'
import type { StatusDetail, TerminalStatus, TerminalTarget } from '@/modules/terminal/types'

const props = defineProps<{
  sessionId: string
  target: TerminalTarget
  fontSize: number
  active: boolean
}>()
const emit = defineEmits<{ status: [status: TerminalStatus, detail: StatusDetail] }>()

const WS_CLOSE_SUDO_REQUIRED = 4403
const el = ref<HTMLElement | null>(null)
let term: Terminal | null = null
let fit: FitAddon | null = null
let socket: WebSocket | null = null
let observer: ResizeObserver | null = null

function sendFrame(frame: Record<string, unknown>): void {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(frame))
}

function fitNow(): void {
  if (!props.active || !el.value?.offsetParent) return // hidden tabs have no size
  try {
    fit?.fit()
  } catch {
    // the container is not laid out yet
  }
}

function connect(): void {
  if (!term) return
  socket?.close(1000)
  let reported = false
  const ws = new WebSocket(wsUrl(`/ws/terminal/${props.sessionId}/`))
  ws.binaryType = 'arraybuffer'
  socket = ws
  emit('status', 'connecting', {})
  ws.onopen = () => {
    fitNow()
    ws.send(
      JSON.stringify({
        type: 'start',
        ...props.target,
        container: props.target.container || null,
        cols: term?.cols ?? 120,
        rows: term?.rows ?? 32,
      }),
    )
  }
  ws.onmessage = (event: MessageEvent<ArrayBuffer | string>) => {
    if (event.data instanceof ArrayBuffer) {
      term?.write(new Uint8Array(event.data))
      return
    }
    let frame: { type?: string; code?: number | string; fields?: string[] }
    try {
      frame = JSON.parse(event.data) as typeof frame
    } catch {
      return
    }
    if (frame.type === 'started') emit('status', 'open', {})
    else if (frame.type === 'exit') {
      reported = true
      emit('status', 'exited', { code: frame.code })
    } else if (frame.type === 'error') {
      reported = true
      emit('status', 'error', { code: frame.code, fields: frame.fields ?? [] })
    }
  }
  ws.onclose = (event: CloseEvent) => {
    if (socket !== ws || reported) return
    if (event.code === WS_CLOSE_SUDO_REQUIRED) emit('status', 'error', { code: 'sudo' })
    else emit('status', 'closed', {})
  }
}

function copySelection(): void {
  const selection = term?.getSelection()
  if (selection) void navigator.clipboard?.writeText(selection).catch(() => undefined)
}

function pasteClipboard(): void {
  void navigator.clipboard
    ?.readText()
    .then((text) => term?.paste(text))
    .catch(() => undefined)
}

onMounted(() => {
  if (!el.value) return
  term = new Terminal({
    cursorBlink: true,
    fontSize: props.fontSize,
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace',
    scrollback: 5000,
    allowProposedApi: false,
    theme: { background: '#16181d', foreground: '#e6e6e6', cursor: '#e6e6e6' },
  })
  fit = new FitAddon()
  term.loadAddon(fit)
  term.open(el.value)
  term.attachCustomKeyEventHandler((event: KeyboardEvent) => {
    if (event.type !== 'keydown' || !event.ctrlKey || !event.shiftKey) return true
    if (event.code === 'KeyC') {
      copySelection()
      return false
    }
    if (event.code === 'KeyV') {
      pasteClipboard()
      return false
    }
    return true
  })
  term.onData((data) => sendFrame({ type: 'input', data }))
  term.onResize(({ cols, rows }) => sendFrame({ type: 'resize', cols, rows }))
  observer = new ResizeObserver(() => fitNow())
  observer.observe(el.value)
  fitNow()
  connect()
  if (props.active) term.focus()
})

watch(
  () => props.active,
  async (active) => {
    if (!active) return
    await nextTick()
    fitNow()
    term?.focus()
  },
)

watch(
  () => props.fontSize,
  (size) => {
    if (!term) return
    term.options.fontSize = size
    fitNow()
  },
)

onBeforeUnmount(() => {
  observer?.disconnect()
  const ws = socket
  socket = null
  ws?.close(1000)
  term?.dispose()
  term = null
})

defineExpose({
  /** Bracketed paste: the shell receives the text but does not run it. */
  insert: (text: string) => term?.paste(text),
  /** Type the command and press Enter. */
  run: (command: string) => {
    const line = command.replace(/\r?\n$/, '').replace(/\r?\n/g, '\r')
    sendFrame({ type: 'input', data: `${line}\r` })
    term?.focus()
  },
  reconnect: () => {
    term?.reset()
    connect()
  },
  focus: () => term?.focus(),
})
</script>

<template>
  <div ref="el" class="ed-terminal" dir="ltr"></div>
</template>

<style scoped>
.ed-terminal {
  position: relative;
  /* xterm parks helper elements at `left: -9999em`; on an RTL page that overflow is scrollable and
     focusing the terminal would scroll the page sideways. `clip` hides it without a scroll box. */
  overflow: clip;
  block-size: 100%;
  inline-size: 100%;
  padding: 0.25rem;
  background: #16181d;
}
</style>
