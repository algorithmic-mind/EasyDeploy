<script setup lang="ts">
/** Live task log over `/ws/tasks/<id>/`: snapshot replay, then streamed lines and status. */
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Task } from '@/api/client'
import { openSocket, type SocketHandle } from '@/api/ws'

interface LogLine {
  seq: number
  text: string
  stream: string
}

type Frame =
  | { type: 'snapshot'; task: Task; lines: string[]; seq: number }
  | { type: 'log'; seq: number; line: string; stream: string }
  | { type: 'status'; task: Task }

const props = defineProps<{ taskId: string }>()
const emit = defineEmits<{ status: [task: Task] }>()
const { t } = useI18n()

const lines = ref<LogLine[]>([])
const connection = ref<'connecting' | 'open' | 'closed'>('connecting')
const box = ref<HTMLElement | null>(null)
let lastSeq = 0
let handle: SocketHandle | null = null

async function scrollToEnd(): Promise<void> {
  await nextTick()
  if (box.value) box.value.scrollTop = box.value.scrollHeight
}

function onFrame(frame: Frame): void {
  if (frame.type === 'snapshot') {
    lines.value = frame.lines.map((text, i) => ({
      seq: i + 1,
      text,
      stream: text.startsWith('ERROR [') ? 'stderr' : 'stdout',
    }))
    lastSeq = frame.seq
    emit('status', frame.task)
  } else if (frame.type === 'log') {
    if (frame.seq <= lastSeq) return // already part of the snapshot
    lastSeq = frame.seq
    lines.value.push({ seq: frame.seq, text: frame.line, stream: frame.stream })
  } else {
    emit('status', frame.task)
  }
  void scrollToEnd()
}

function connect(id: string): void {
  handle?.close()
  lines.value = []
  lastSeq = 0
  handle = openSocket<Frame>(`/ws/tasks/${id}/`, {
    onMessage: onFrame,
    onStatus: (s) => (connection.value = s),
  })
}

watch(() => props.taskId, connect, { immediate: true })
onBeforeUnmount(() => handle?.close())
</script>

<template>
  <div>
    <div v-if="connection === 'closed'" class="alert alert-warning py-1 px-2 small">
      {{ t('tasks.connection_lost') }}
    </div>
    <div ref="box" class="ed-log" dir="ltr" role="log" aria-live="polite">
      <div v-if="lines.length === 0" class="text-secondary">{{ t('tasks.log_empty') }}</div>
      <div
        v-for="line in lines"
        :key="line.seq"
        :class="{ 'ed-log-stderr': line.stream === 'stderr' }"
        v-text="line.text"
      ></div>
    </div>
  </div>
</template>
