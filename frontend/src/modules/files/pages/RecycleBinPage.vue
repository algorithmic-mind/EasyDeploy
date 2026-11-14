<script setup lang="ts">
/** Files → Recycle bin: restore or permanently delete (sudo mode) (§9.9). */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { filesApi, type RecycleItem } from '@/api/client'
import EmptyState from '@/components/EmptyState.vue'
import { useApiError } from '@/composables/useApiError'
import { useConfirm } from '@/composables/useConfirm'
import { useSudo } from '@/composables/useSudo'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import { formatBytes, formatDateTime } from '@/utils/format'

const { t } = useI18n()
const toast = useToast()
const apiError = useApiError()
const confirm = useConfirm()
const sudo = useSudo()
const auth = useAuthStore()
const items = ref<RecycleItem[]>([])

async function load(): Promise<void> {
  try {
    items.value = (await filesApi.recycle()).items
  } catch (error) {
    toast.error(apiError.message(error))
  }
}

async function restore(item: RecycleItem): Promise<void> {
  try {
    await filesApi.restore([item.id])
    toast.success(t('files.restored', { path: item.original_path }))
    await load()
  } catch (error) {
    toast.error(apiError.message(error))
  }
}

async function purge(ids: string[] | 'all'): Promise<void> {
  const ok = await confirm({
    title: t('files.purge'),
    message: t('files.purge_confirm'),
    danger: true,
    confirmLabel: t('files.purge'),
  })
  if (!ok) return
  try {
    await sudo.run(() => filesApi.purge(ids === 'all' ? { all: true } : { ids }))
    await load()
  } catch (error) {
    toast.error(apiError.message(error))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex align-items-center mb-3">
      <h1 class="h4 mb-0 flex-grow-1">{{ t('nav.files.recycle_bin') }}</h1>
      <button
        v-if="items.length"
        type="button"
        class="btn btn-sm btn-outline-danger"
        @click="purge('all')"
      >
        {{ t('files.empty_bin') }}
      </button>
    </div>
    <div class="card">
      <EmptyState v-if="items.length === 0" icon="bi-trash" :title="t('files.bin_empty')" />
      <div v-else class="table-responsive">
        <table class="table table-sm align-middle mb-0">
          <thead>
            <tr>
              <th>{{ t('files.original_path') }}</th>
              <th>{{ t('files.deleted_at') }}</th>
              <th class="text-end">{{ t('files.size') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td class="ltr-island">{{ item.original_path }}</td>
              <td class="small">
                {{
                  formatDateTime(
                    new Date(item.deleted_at * 1000).toISOString(),
                    auth.user?.calendar ?? 'gregorian',
                  )
                }}
              </td>
              <td class="text-end small">
                {{ item.kind === 'dir' ? '' : formatBytes(item.size, t) }}
              </td>
              <td class="text-end text-nowrap">
                <button type="button" class="btn btn-sm btn-link" @click="restore(item)">
                  {{ t('files.restore') }}
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-link text-danger"
                  @click="purge([item.id])"
                >
                  {{ t('files.purge') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
