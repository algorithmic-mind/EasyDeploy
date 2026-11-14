/** Task Center state: recent tasks, polling while open or while tasks are active (§5.4). */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { tasksApi, type Task } from '@/api/client'

const ACTIVE = new Set(['pending', 'running'])
const FAST_POLL_MS = 3000
const SLOW_POLL_MS = 20000

export const useTasksStore = defineStore('tasks', () => {
  const items = ref<Task[]>([])
  const open = ref(false)
  const selectedId = ref<string | null>(null)
  let timer: ReturnType<typeof setTimeout> | null = null

  const runningCount = computed(() => items.value.filter((t) => ACTIVE.has(t.status)).length)

  async function load(): Promise<void> {
    try {
      const page = await tasksApi.list({ page_size: 20, ordering: '-created_at' })
      items.value = page.results
    } catch {
      // the next poll retries; errors surface on explicit actions
    }
  }

  function schedule(): void {
    if (timer) clearTimeout(timer)
    const delay = open.value || runningCount.value > 0 ? FAST_POLL_MS : SLOW_POLL_MS
    timer = setTimeout(async () => {
      await load()
      schedule()
    }, delay)
  }

  async function start(): Promise<void> {
    await load()
    schedule()
  }

  function stop(): void {
    if (timer) clearTimeout(timer)
    timer = null
    items.value = []
  }

  function show(taskId: string | null = null): void {
    selectedId.value = taskId
    open.value = true
    void load()
    schedule()
  }

  /** Called after an action returns 202 {task_id}: open the live log right away (§10.6). */
  async function track(taskId: string): Promise<void> {
    await load()
    show(taskId)
  }

  function upsert(task: Task): void {
    const index = items.value.findIndex((t) => t.id === task.id)
    if (index >= 0) items.value.splice(index, 1, task)
    else items.value.unshift(task)
  }

  return { items, open, selectedId, runningCount, load, start, stop, show, track, upsert }
})
