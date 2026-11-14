<script setup lang="ts">
/** Host → Services: systemd units, actions and journal tail (§9.11). */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { hostApi, type JournalEntry, type UnitRow } from '@/api/client'
import EdOffcanvas from '@/components/ui/EdOffcanvas.vue'
import { useApiError } from '@/composables/useApiError'
import { useConfirm } from '@/composables/useConfirm'
import { useToast } from '@/composables/useToast'

type Action = 'start' | 'stop' | 'restart' | 'enable' | 'disable'

const { t } = useI18n()
const toast = useToast()
const apiError = useApiError()
const confirm = useConfirm()

const units = ref<UnitRow[]>([])
const filter = ref<'all' | 'running' | 'failed'>('running')
const search = ref('')
const busy = ref<string | null>(null)
const journalUnit = ref<string | null>(null)
const journal = ref<JournalEntry[]>([])
const journalOpen = computed({
  get: () => journalUnit.value !== null,
  set: (v: boolean) => {
    if (!v) journalUnit.value = null
  },
})

const shown = computed(() => {
  const q = search.value.trim().toLowerCase()
  return units.value.filter((u) => {
    if (filter.value === 'running' && u.active_state !== 'active') return false
    if (filter.value === 'failed' && u.active_state !== 'failed') return false
    return !q || u.unit.toLowerCase().includes(q) || u.description.toLowerCase().includes(q)
  })
})

const stateClass = (s: string) =>
  s === 'active' ? 'text-bg-success' : s === 'failed' ? 'text-bg-danger' : 'text-bg-secondary'

async function load(): Promise<void> {
  try {
    units.value = (await hostApi.services()).units as unknown as UnitRow[]
  } catch (error) {
    toast.error(apiError.message(error))
  }
}

function allowed(u: UnitRow, action: Action): boolean {
  if (u.unit.startsWith('easydeploy-')) return false
  return !(u.protected && (action === 'stop' || action === 'disable'))
}

async function run(u: UnitRow, action: Action): Promise<void> {
  if (action === 'stop' || action === 'disable') {
    const ok = await confirm({
      title: t(`host.actions.${action}`),
      message: t('host.service_confirm', { unit: u.unit, action: t(`host.actions.${action}`) }),
      danger: true,
    })
    if (!ok) return
  }
  busy.value = u.unit
  try {
    await hostApi.serviceAction(u.unit, action)
    toast.success(t('host.service_done', { unit: u.unit }))
    await load()
  } catch (error) {
    toast.error(apiError.message(error))
  } finally {
    busy.value = null
  }
}

async function showJournal(u: UnitRow): Promise<void> {
  journalUnit.value = u.unit
  journal.value = []
  try {
    journal.value = (await hostApi.journal({ unit: u.unit, lines: 200 }))
      .entries as unknown as JournalEntry[]
  } catch (error) {
    toast.error(apiError.message(error))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <h1 class="h4 mb-3">{{ t('nav.host.services') }}</h1>
    <div class="card">
      <div class="card-body d-flex flex-wrap gap-2 border-bottom">
        <div class="btn-group btn-group-sm" role="group">
          <button
            v-for="f in ['running', 'failed', 'all'] as const"
            :key="f"
            type="button"
            class="btn"
            :class="filter === f ? 'btn-primary' : 'btn-outline-secondary'"
            @click="filter = f"
          >
            {{ t(`host.filter.${f}`) }}
          </button>
        </div>
        <input
          v-model="search"
          class="form-control form-control-sm"
          style="max-width: 18rem"
          :placeholder="t('common.search')"
          :aria-label="t('common.search')"
        />
        <button type="button" class="btn btn-sm btn-outline-secondary ms-auto" @click="load">
          <i class="bi bi-arrow-clockwise" aria-hidden="true"></i>
        </button>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-hover align-middle mb-0">
          <thead>
            <tr>
              <th>{{ t('host.unit') }}</th>
              <th class="d-none d-md-table-cell">{{ t('host.description') }}</th>
              <th>{{ t('host.state') }}</th>
              <th>{{ t('host.startup') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in shown" :key="u.unit">
              <td class="ltr-island">
                {{ u.unit }}
                <i
                  v-if="u.protected"
                  class="bi bi-shield-lock text-body-secondary"
                  :title="t('host.protected')"
                ></i>
              </td>
              <td class="d-none d-md-table-cell small text-body-secondary">{{ u.description }}</td>
              <td>
                <span class="badge" :class="stateClass(u.active_state)">{{ u.active_state }}</span>
                <small class="text-body-secondary ms-1">{{ u.sub_state }}</small>
              </td>
              <td class="small">{{ u.unit_file_state }}</td>
              <td class="text-end text-nowrap">
                <button
                  v-for="a in ['start', 'restart', 'stop', 'enable', 'disable'] as const"
                  :key="a"
                  type="button"
                  class="btn btn-sm btn-link px-1"
                  :disabled="busy === u.unit || !allowed(u, a)"
                  @click="run(u, a)"
                >
                  {{ t(`host.actions.${a}`) }}
                </button>
                <button type="button" class="btn btn-sm btn-link px-1" @click="showJournal(u)">
                  {{ t('host.logs') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <EdOffcanvas v-model="journalOpen" :title="journalUnit ?? ''">
      <div class="ed-log" dir="ltr">
        <div v-for="(e, i) in journal" :key="i" :class="{ 'ed-log-stderr': e.priority <= 3 }">
          {{ new Date(e.timestamp * 1000).toISOString().slice(0, 19) }} {{ e.message }}
        </div>
      </div>
    </EdOffcanvas>
  </div>
</template>
