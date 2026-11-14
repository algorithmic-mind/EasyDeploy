<script setup lang="ts">
/** Global Task Center drawer (§5.4): recent tasks, live log of the selected one, cancel. */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { tasksApi, type Task } from '@/api/client'
import EmptyState from '@/components/EmptyState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import TaskLogViewer from '@/components/TaskLogViewer.vue'
import EdOffcanvas from '@/components/ui/EdOffcanvas.vue'
import { useApiError } from '@/composables/useApiError'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import { useTasksStore } from '@/stores/tasks'
import { formatDateTime } from '@/utils/format'

const tasks = useTasksStore()
const auth = useAuthStore()
const toast = useToast()
const apiError = useApiError()
const { t, te } = useI18n()

const selected = computed(() => tasks.items.find((task) => task.id === tasks.selectedId) ?? null)

function title(task: Task): string {
  const params = (task.title_params ?? {}) as Record<string, unknown>
  return te(task.title_key) ? t(task.title_key, params) : task.kind
}

function errorText(task: Task): string {
  const error = (task.error ?? {}) as { code?: string; message?: string }
  return error.message ?? error.code ?? ''
}

function when(task: Task): string {
  return formatDateTime(task.created_at, auth.user?.calendar ?? 'gregorian')
}

async function cancel(task: Task): Promise<void> {
  try {
    tasks.upsert(await tasksApi.cancel(task.id))
  } catch (error) {
    toast.error(apiError.message(error), apiError.requestId(error))
  }
}
</script>

<template>
  <EdOffcanvas v-model="tasks.open" :title="t('tasks.center_title')">
    <template v-if="tasks.selectedId">
      <button type="button" class="btn btn-sm btn-link px-0 mb-2" @click="tasks.selectedId = null">
        <i class="bi bi-arrow-left ed-flip-rtl" aria-hidden="true"></i>
        {{ t('tasks.back_to_list') }}
      </button>
      <div v-if="selected" class="d-flex align-items-center gap-2 mb-2">
        <strong class="flex-grow-1">{{ title(selected) }}</strong>
        <StatusBadge :status="selected.status" />
      </div>
      <div
        v-if="selected && selected.status === 'running'"
        class="progress mb-2"
        role="progressbar"
        :aria-valuenow="selected.progress"
        aria-valuemin="0"
        aria-valuemax="100"
        style="height: 0.4rem"
      >
        <div class="progress-bar" :style="{ width: `${selected.progress}%` }"></div>
      </div>
      <TaskLogViewer :task-id="tasks.selectedId" @status="tasks.upsert" />
      <div v-if="selected?.error" class="alert alert-danger mt-2 small mb-0">
        {{ errorText(selected) }}
      </div>
      <button
        v-if="selected && (selected.status === 'running' || selected.status === 'pending')"
        type="button"
        class="btn btn-outline-danger btn-sm mt-2"
        @click="cancel(selected)"
      >
        {{ t('tasks.cancel') }}
      </button>
    </template>

    <template v-else>
      <EmptyState v-if="tasks.items.length === 0" icon="bi-list-task" :title="t('tasks.empty')" />
      <div v-else class="list-group list-group-flush">
        <button
          v-for="task in tasks.items"
          :key="task.id"
          type="button"
          class="list-group-item list-group-item-action"
          @click="tasks.selectedId = task.id"
        >
          <div class="d-flex align-items-center gap-2">
            <span class="flex-grow-1 text-truncate">{{ title(task) }}</span>
            <StatusBadge :status="task.status" />
          </div>
          <small class="text-body-secondary">{{ when(task) }}</small>
        </button>
      </div>
    </template>
  </EdOffcanvas>
</template>
