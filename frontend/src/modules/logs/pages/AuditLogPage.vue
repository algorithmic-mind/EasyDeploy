<script setup lang="ts">
/** Logs → Audit log and Login log (one page, two modes chosen by the route) (§9.14). */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { logsApi, type AuditRow, type LoginRow } from '@/api/client'
import EmptyState from '@/components/EmptyState.vue'
import { useApiError } from '@/composables/useApiError'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils/format'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const apiError = useApiError()

const mode = computed(() => (route.path.endsWith('/login') ? 'login' : 'audit'))
const audit = ref<AuditRow[]>([])
const logins = ref<LoginRow[]>([])
const count = ref(0)
const page = ref(1)
const search = ref('')
const error = ref('')
const PAGE_SIZE = 50
const pages = computed(() => Math.max(1, Math.ceil(count.value / PAGE_SIZE)))
const when = (ts: string) => formatDateTime(ts, auth.user?.calendar ?? 'gregorian')

async function load(): Promise<void> {
  error.value = ''
  const query = { page: page.value, page_size: PAGE_SIZE, search: search.value }
  try {
    if (mode.value === 'audit') {
      const res = await logsApi.audit(query)
      audit.value = res.results
      count.value = res.count
    } else {
      const res = await logsApi.logins(query)
      logins.value = res.results
      count.value = res.count
    }
  } catch (err) {
    error.value = apiError.message(err)
  }
}

watch([page, mode], load)
watch(search, () => {
  page.value = 1
  void load()
})
onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <h1 class="h4 mb-0 flex-grow-1">
        {{ t(mode === 'audit' ? 'nav.logs.audit' : 'nav.logs.login') }}
      </h1>
      <input
        v-model.lazy="search"
        class="form-control form-control-sm"
        style="max-width: 16rem"
        :placeholder="t('common.search')"
        :aria-label="t('common.search')"
      />
    </div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div class="card">
      <EmptyState v-if="count === 0" icon="bi-journal" :title="t('common.empty')" />
      <div v-else class="table-responsive">
        <table v-if="mode === 'audit'" class="table table-sm align-middle mb-0">
          <thead>
            <tr>
              <th>{{ t('logs.time') }}</th>
              <th>{{ t('logs.actor') }}</th>
              <th>{{ t('logs.action') }}</th>
              <th>{{ t('logs.resource') }}</th>
              <th>{{ t('logs.ip') }}</th>
              <th>{{ t('logs.result') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in audit" :key="row.id">
              <td class="text-nowrap small">{{ when(row.created_at) }}</td>
              <td class="ltr-island">{{ row.actor_label }}</td>
              <td>
                <code>{{ row.action }}</code>
              </td>
              <td class="small ltr-island">{{ row.resource_type }} {{ row.resource_id }}</td>
              <td class="small ltr-island">{{ row.ip }}</td>
              <td>
                <span
                  class="badge"
                  :class="row.result === 'success' ? 'text-bg-success' : 'text-bg-danger'"
                >
                  {{ t(`logs.results.${row.result}`) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
        <table v-else class="table table-sm align-middle mb-0">
          <thead>
            <tr>
              <th>{{ t('logs.time') }}</th>
              <th>{{ t('auth.username') }}</th>
              <th>{{ t('logs.ip') }}</th>
              <th>{{ t('logs.result') }}</th>
              <th class="d-none d-md-table-cell">{{ t('logs.user_agent') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in logins" :key="row.id">
              <td class="text-nowrap small">{{ when(row.created_at) }}</td>
              <td class="ltr-island">{{ row.username }}</td>
              <td class="small ltr-island">{{ row.ip }}</td>
              <td>
                <span class="badge" :class="row.success ? 'text-bg-success' : 'text-bg-danger'">
                  {{ row.success ? t('logs.results.success') : t('logs.results.failure') }}
                </span>
                <small v-if="!row.success" class="text-body-secondary ms-1">{{ row.reason }}</small>
              </td>
              <td
                class="d-none d-md-table-cell small text-truncate ltr-island"
                style="max-width: 20rem"
              >
                {{ row.user_agent }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="pages > 1" class="card-footer d-flex justify-content-between align-items-center">
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary"
          :disabled="page <= 1"
          @click="page--"
        >
          {{ t('common.previous') }}
        </button>
        <span class="small">{{ t('common.page_of', { page, pages }) }}</span>
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary"
          :disabled="page >= pages"
          @click="page++"
        >
          {{ t('common.next') }}
        </button>
      </div>
    </div>
  </div>
</template>
