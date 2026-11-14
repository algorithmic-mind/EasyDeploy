<script setup lang="ts">
/** Host → Processes: list, sort, filter, terminate / kill (§9.11). */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { hostApi, type ProcessRow } from '@/api/client'
import { useApiError } from '@/composables/useApiError'
import { useConfirm } from '@/composables/useConfirm'
import { useToast } from '@/composables/useToast'
import { formatBytes } from '@/utils/format'

const { t } = useI18n()
const toast = useToast()
const apiError = useApiError()
const confirm = useConfirm()

const rows = ref<ProcessRow[]>([])
const total = ref(0)
const sort = ref<'cpu' | 'memory' | 'pid' | 'name'>('cpu')
const search = ref('')
const auto = ref(true)
const loading = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter(
    (p) =>
      p.name.toLowerCase().includes(q) ||
      p.cmdline.toLowerCase().includes(q) ||
      p.username.toLowerCase().includes(q) ||
      String(p.pid) === q,
  )
})

async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await hostApi.processes(sort.value)
    rows.value = result.processes as unknown as ProcessRow[]
    total.value = result.total
  } catch (error) {
    toast.error(apiError.message(error))
    auto.value = false
  } finally {
    loading.value = false
  }
}

async function signal(p: ProcessRow, sig: 'TERM' | 'KILL'): Promise<void> {
  const ok = await confirm({
    title: t(sig === 'KILL' ? 'host.kill' : 'host.terminate'),
    message: t('host.signal_confirm', { name: p.name, pid: p.pid }),
    danger: true,
    confirmLabel: t(sig === 'KILL' ? 'host.kill' : 'host.terminate'),
  })
  if (!ok) return
  try {
    await hostApi.signal(p.pid, sig)
    toast.success(t('host.signal_sent', { pid: p.pid }))
    await load()
  } catch (error) {
    toast.error(apiError.message(error))
  }
}

function schedule(): void {
  if (timer) clearInterval(timer)
  timer = auto.value ? setInterval(load, 5000) : null
}

watch(sort, load)
watch(auto, schedule)
onMounted(async () => {
  await load()
  schedule()
})
onBeforeUnmount(() => timer && clearInterval(timer))
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <h1 class="h4 mb-0 flex-grow-1">{{ t('nav.host.processes') }}</h1>
      <span class="text-body-secondary small">{{ t('host.total', { n: total }) }}</span>
    </div>
    <div class="card">
      <div class="card-body d-flex flex-wrap gap-2 border-bottom">
        <input
          v-model="search"
          class="form-control form-control-sm"
          style="max-width: 18rem"
          :placeholder="t('common.search')"
          :aria-label="t('common.search')"
        />
        <select
          v-model="sort"
          class="form-select form-select-sm w-auto"
          :aria-label="t('host.sort')"
        >
          <option value="cpu">{{ t('host.sort_cpu') }}</option>
          <option value="memory">{{ t('host.sort_memory') }}</option>
          <option value="pid">{{ t('host.sort_pid') }}</option>
          <option value="name">{{ t('host.sort_name') }}</option>
        </select>
        <div class="form-check form-switch ms-auto">
          <input id="proc-auto" v-model="auto" class="form-check-input" type="checkbox" />
          <label class="form-check-label small" for="proc-auto">{{
            t('common.auto_refresh')
          }}</label>
        </div>
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary"
          :disabled="loading"
          @click="load"
        >
          <i class="bi bi-arrow-clockwise" aria-hidden="true"></i>
        </button>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-hover align-middle mb-0">
          <thead>
            <tr>
              <th>{{ t('host.pid') }}</th>
              <th>{{ t('host.name') }}</th>
              <th>{{ t('host.user') }}</th>
              <th class="text-end">{{ t('monitoring.cpu') }}</th>
              <th class="text-end">{{ t('monitoring.memory') }}</th>
              <th class="d-none d-lg-table-cell">{{ t('host.command') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in filtered" :key="p.pid">
              <td class="ltr-island">{{ p.pid }}</td>
              <td class="ltr-island">{{ p.name }}</td>
              <td class="ltr-island">{{ p.username }}</td>
              <td class="text-end">{{ p.cpu_percent.toFixed(1) }}%</td>
              <td class="text-end">{{ formatBytes(p.memory_rss, t) }}</td>
              <td
                class="d-none d-lg-table-cell text-truncate small ltr-island"
                style="max-width: 28rem"
              >
                {{ p.cmdline }}
              </td>
              <td class="text-end text-nowrap">
                <button type="button" class="btn btn-sm btn-link" @click="signal(p, 'TERM')">
                  {{ t('host.terminate') }}
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-link text-danger"
                  @click="signal(p, 'KILL')"
                >
                  {{ t('host.kill') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
