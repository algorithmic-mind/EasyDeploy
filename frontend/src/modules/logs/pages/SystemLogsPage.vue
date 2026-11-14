<script setup lang="ts">
/** Logs → System logs: journald by unit / priority / time / text, with live follow (§9.14). */
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { hostApi, type JournalEntry } from '@/api/client'
import { useApiError } from '@/composables/useApiError'

const { t } = useI18n()
const apiError = useApiError()

const filters = reactive({ unit: '', priority: '', since: '', grep: '', lines: 300 })
const entries = ref<JournalEntry[]>([])
const error = ref('')
const loading = ref(false)
const follow = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const PRIORITIES = ['0', '1', '2', '3', '4', '5', '6', '7']
const source = (e: JournalEntry) => `${e.identifier || e.unit}${e.pid ? `[${e.pid}]` : ''}`
const levelClass = (p: number) => (p <= 3 ? 'ed-log-stderr' : p === 4 ? 'text-warning' : '')

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const query: Record<string, string | number> = { lines: filters.lines }
    if (filters.unit) query.unit = filters.unit
    if (filters.priority) query.priority = filters.priority
    if (filters.since) query.since = filters.since.replace('T', ' ')
    if (filters.grep) query.grep = filters.grep
    entries.value = (await hostApi.journal(query)).entries as unknown as JournalEntry[]
  } catch (err) {
    error.value = apiError.message(err)
  } finally {
    loading.value = false
  }
}

watch(follow, (on) => {
  if (timer) clearInterval(timer)
  timer = on ? setInterval(load, 5000) : null
})
onMounted(load)
onBeforeUnmount(() => timer && clearInterval(timer))
</script>

<template>
  <div>
    <h1 class="h4 mb-3">{{ t('nav.logs.system') }}</h1>
    <form class="card card-body mb-3 row g-2 flex-row" @submit.prevent="load">
      <div class="col-6 col-md-3">
        <label class="form-label small" for="j-unit">{{ t('host.unit') }}</label>
        <input
          id="j-unit"
          v-model.trim="filters.unit"
          class="form-control form-control-sm ltr-island"
          placeholder="nginx"
        />
      </div>
      <div class="col-6 col-md-2">
        <label class="form-label small" for="j-prio">{{ t('logs.priority') }}</label>
        <select id="j-prio" v-model="filters.priority" class="form-select form-select-sm">
          <option value="">{{ t('logs.all') }}</option>
          <option v-for="p in PRIORITIES" :key="p" :value="p">
            {{ t(`logs.priorities.${p}`) }}
          </option>
        </select>
      </div>
      <div class="col-6 col-md-3">
        <label class="form-label small" for="j-since">{{ t('logs.since') }}</label>
        <input
          id="j-since"
          v-model="filters.since"
          type="datetime-local"
          class="form-control form-control-sm"
        />
      </div>
      <div class="col-6 col-md-2">
        <label class="form-label small" for="j-grep">{{ t('common.search') }}</label>
        <input id="j-grep" v-model="filters.grep" class="form-control form-control-sm" />
      </div>
      <div class="col-12 col-md-2 d-flex align-items-end gap-2">
        <button type="submit" class="btn btn-sm btn-primary" :disabled="loading">
          {{ t('common.refresh') }}
        </button>
        <div class="form-check form-switch mb-1">
          <input id="j-follow" v-model="follow" class="form-check-input" type="checkbox" />
          <label class="form-check-label small" for="j-follow">{{ t('logs.follow') }}</label>
        </div>
      </div>
    </form>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div class="ed-log" dir="ltr" style="max-height: 70vh">
      <div v-if="entries.length === 0" class="text-secondary">{{ t('common.empty') }}</div>
      <div v-for="(e, i) in entries" :key="i" :class="levelClass(e.priority)">
        {{ new Date(e.timestamp * 1000).toISOString().replace('T', ' ').slice(0, 19) }}
        {{ source(e) }}: {{ e.message }}
      </div>
    </div>
  </div>
</template>
