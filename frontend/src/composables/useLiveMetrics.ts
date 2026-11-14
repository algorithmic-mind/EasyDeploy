/** Live host metrics from `/ws/monitor/live/` (one frame every ~3 s while mounted). */
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { openSocket, type SocketHandle } from '@/api/ws'

export interface DiskUsage {
  mountpoint: string
  device: string
  fstype: string
  total: number
  used: number
  percent: number
}

export interface TopProcess {
  pid: number
  name: string
  username: string
  cpu_percent: number
  memory_rss: number
}

export interface LiveMetrics {
  timestamp: number
  cpu_percent: number
  cpu_per_core: number[]
  load1: number
  load5: number
  load15: number
  memory_total: number
  memory_used: number
  swap_total: number
  swap_used: number
  disks: DiskUsage[]
  disk_read_bps: number
  disk_write_bps: number
  net_rx_bps: number
  net_tx_bps: number
  top_cpu: TopProcess[]
  top_memory: TopProcess[]
  uptime_seconds: number
}

type Frame = { type: 'metrics'; data: LiveMetrics } | { type: 'error'; code: string }

const HISTORY = 40

export function useLiveMetrics() {
  const current = ref<LiveMetrics | null>(null)
  const recent = ref<LiveMetrics[]>([])
  const error = ref<string | null>(null)
  let handle: SocketHandle | null = null

  onMounted(() => {
    handle = openSocket<Frame>('/ws/monitor/live/', {
      onMessage: (frame) => {
        if (frame.type === 'error') {
          error.value = frame.code
          return
        }
        error.value = null
        current.value = frame.data
        recent.value = [...recent.value.slice(-(HISTORY - 1)), frame.data]
      },
    })
  })
  onBeforeUnmount(() => handle?.close())

  return { current, recent, error }
}
