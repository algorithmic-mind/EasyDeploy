<script setup lang="ts">
/** Overview (Phase 0): static host information from the agent + diagnostics task. */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { dashboardApi, tasksApi, type SystemInfo } from '@/api/client'
import { useApiError } from '@/composables/useApiError'
import { useToast } from '@/composables/useToast'
import { useTasksStore } from '@/stores/tasks'
import { formatBytes, formatDuration } from '@/utils/format'

const { t } = useI18n()
const tasks = useTasksStore()
const toast = useToast()
const apiError = useApiError()

const info = ref<SystemInfo | null>(null)
const loading = ref(true)
const agentDown = ref(false)
const starting = ref(false)

const rows = computed(() => {
  const i = info.value
  return [
    { key: 'hostname', value: i?.hostname },
    { key: 'os', value: i?.os_name },
    { key: 'kernel', value: i?.kernel },
    { key: 'arch', value: i?.arch },
    {
      key: 'cpu',
      value: i
        ? t('dashboard.cpu_value', {
            model: i.cpu_model,
            cores: i.cpu_cores,
            threads: i.cpu_threads,
          })
        : '',
    },
    { key: 'memory', value: i ? formatBytes(i.memory_total, t) : '' },
    { key: 'swap', value: i ? formatBytes(i.swap_total, t) : '' },
    { key: 'uptime', value: i ? formatDuration(i.uptime_seconds, t) : '' },
  ]
})

async function load(): Promise<void> {
  loading.value = true
  agentDown.value = false
  try {
    info.value = await dashboardApi.systemInfo()
  } catch {
    agentDown.value = true
  } finally {
    loading.value = false
  }
}

async function runDiagnostics(): Promise<void> {
  starting.value = true
  try {
    const { task_id } = await tasksApi.diagnostics()
    await tasks.track(task_id)
  } catch (error) {
    toast.error(apiError.message(error), apiError.requestId(error))
  } finally {
    starting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex align-items-center mb-4">
      <h1 class="h4 mb-0 flex-grow-1">{{ t('dashboard.title') }}</h1>
      <button type="button" class="btn btn-outline-secondary btn-sm" @click="load">
        <i class="bi bi-arrow-clockwise" aria-hidden="true"></i> {{ t('common.refresh') }}
      </button>
    </div>

    <div class="row g-3">
      <div class="col-12 col-xl-8">
        <div class="card h-100">
          <div class="card-header fw-semibold">{{ t('dashboard.system') }}</div>
          <div class="card-body">
            <div v-if="agentDown" class="alert alert-warning mb-0">
              {{ t('dashboard.agent_unavailable') }}
              <button type="button" class="btn btn-link btn-sm" @click="load">
                {{ t('common.retry') }}
              </button>
            </div>
            <dl v-else class="row mb-0">
              <template v-for="row in rows" :key="row.key">
                <dt class="col-sm-4 text-body-secondary fw-normal">
                  {{ t(`dashboard.${row.key}`) }}
                </dt>
                <dd class="col-sm-8">
                  <span v-if="loading" class="ed-skeleton"></span>
                  <span v-else class="ltr-island">{{ row.value }}</span>
                </dd>
              </template>
            </dl>
          </div>
        </div>
      </div>

      <div class="col-12 col-xl-4 d-flex flex-column gap-3">
        <div class="card">
          <div class="card-header fw-semibold">{{ t('dashboard.versions') }}</div>
          <ul class="list-group list-group-flush">
            <li class="list-group-item d-flex justify-content-between">
              <span>{{ t('dashboard.panel_version') }}</span>
              <code>{{ info?.panel_version ?? '—' }}</code>
            </li>
            <li class="list-group-item d-flex justify-content-between">
              <span>{{ t('dashboard.agent_version') }}</span>
              <code>{{ info?.agent_version ?? '—' }}</code>
            </li>
          </ul>
        </div>
        <div class="card">
          <div class="card-header fw-semibold">{{ t('dashboard.diagnostics') }}</div>
          <div class="card-body">
            <p class="small text-body-secondary">{{ t('dashboard.diagnostics_text') }}</p>
            <button
              type="button"
              class="btn btn-primary btn-sm"
              :disabled="starting"
              @click="runDiagnostics"
            >
              <i class="bi bi-activity" aria-hidden="true"></i> {{ t('dashboard.run_diagnostics') }}
            </button>
          </div>
        </div>
        <p class="small text-body-secondary mb-0">
          <i class="bi bi-graph-up" aria-hidden="true"></i> {{ t('dashboard.live_metrics_soon') }}
        </p>
      </div>
    </div>
  </div>
</template>
