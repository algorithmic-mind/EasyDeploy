<script setup lang="ts">
/** Logs → Task log: every background task with status and a live/replayed log (§5.4, §9.14). */
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { tasksApi, type Task, type TaskStatus } from '@/api/client'
import EmptyState from '@/components/EmptyState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useApiError } from '@/composables/useApiError'
import { useAuthStore } from '@/stores/auth'
import { useTasksStore } from '@/stores/tasks'
import { formatDateTime } from '@/utils/format'

const { t, te } = useI18n()
const auth = useAuthStore()
const tasksStore = useTasksStore()
const apiError = useApiError()

const rows = ref<Task[]>([])
const count = ref(0)
const status = ref<TaskStatus | ''>('')
const page = ref(1)
const error = ref('')
const PAGE_SIZE = 50

const title = (task: Task) =>
  te(task.title_key)
    ? t(task.title_key, (task.title_params ?? {}) as Record<string, unknown>)
    : task.kind
const when = (ts: string | null) => formatDateTime(ts, auth.user?.calendar ?? 'gregorian')
const duration = (task: Task) =>
  task.started_at && task.finished_at
    ? `${Math.max(0, Math.round((Date.parse(task.finished_at) - Date.parse(task.started_at)) / 1000))}s`
    : ''

async function load(): Promise<void> {
  try {
    const res = await tasksApi.list({
      page: page.value,
      page_size: PAGE_SIZE,
      status: status.value,
      ordering: '-created_at',
    })
    rows.value = res.results
    count.value = res.count
  } catch (err) {
    error.value = apiError.message(err)
  }
}

watch([status, page], load)
onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <h1 class="h4 mb-0 flex-grow-1">{{ t('nav.logs.tasks') }}</h1>
      <select
        v-model="status"
        class="form-select form-select-sm w-auto"
        :aria-label="t('logs.result')"
      >
        <option value="">{{ t('logs.all') }}</option>
        <option
          v-for="s in ['running', 'succeeded', 'failed', 'cancelled', 'pending']"
          :key="s"
          :value="s"
        >
          {{ t(`tasks.status.${s}`) }}
        </option>
      </select>
    </div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div class="card">
      <EmptyState v-if="count === 0" icon="bi-list-task" :title="t('tasks.empty')" />
      <div v-else class="table-responsive">
        <table class="table table-sm table-hover align-middle mb-0">
          <thead>
            <tr>
              <th>{{ t('logs.time') }}</th>
              <th>{{ t('logs.task') }}</th>
              <th>{{ t('logs.result') }}</th>
              <th>{{ t('logs.duration') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in rows" :key="task.id">
              <td class="text-nowrap small">{{ when(task.created_at) }}</td>
              <td>{{ title(task) }}</td>
              <td><StatusBadge :status="task.status" /></td>
              <td class="small">{{ duration(task) }}</td>
              <td class="text-end">
                <button type="button" class="btn btn-sm btn-link" @click="tasksStore.show(task.id)">
                  {{ t('tasks.view_log') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="count > PAGE_SIZE" class="card-footer d-flex justify-content-between">
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary"
          :disabled="page <= 1"
          @click="page--"
        >
          {{ t('common.previous') }}
        </button>
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary"
          :disabled="page * PAGE_SIZE >= count"
          @click="page++"
        >
          {{ t('common.next') }}
        </button>
      </div>
    </div>
  </div>
</template>
