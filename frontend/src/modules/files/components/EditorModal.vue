<script setup lang="ts">
/** Open a text file in Monaco, save with conflict detection (§9.9). */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { filesApi } from '@/api/client'
import { ApiError } from '@/api/http'
import EdModal from '@/components/ui/EdModal.vue'
import { useApiError } from '@/composables/useApiError'
import { useTheme } from '@/composables/useTheme'
import { useToast } from '@/composables/useToast'
import CodeEditor from '@/modules/files/components/CodeEditor.vue'

const props = defineProps<{ path: string | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const { t } = useI18n()
const toast = useToast()
const apiError = useApiError()
const { theme } = useTheme()

const content = ref('')
const original = ref('')
const sha = ref<string | undefined>(undefined)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const visible = computed({
  get: () => props.path !== null,
  set: (v: boolean) => {
    if (!v) emit('close')
  },
})
const dirty = computed(() => content.value !== original.value)
const dark = computed(
  () => theme.value === 'dark' || document.documentElement.getAttribute('data-bs-theme') === 'dark',
)

watch(
  () => props.path,
  async (path) => {
    if (!path) return
    loading.value = true
    error.value = ''
    try {
      const file = await filesApi.read(path)
      content.value = original.value = String(file.content ?? '')
      sha.value = String(file.sha256 ?? '')
    } catch (err) {
      error.value = apiError.message(err)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

async function save(): Promise<void> {
  if (!props.path || saving.value) return
  saving.value = true
  try {
    const result = await filesApi.write({
      path: props.path,
      content: content.value,
      expected_sha256: sha.value,
    })
    sha.value = String(result.sha256 ?? '')
    original.value = content.value
    toast.success(t('common.saved'))
    emit('saved')
  } catch (err) {
    if (err instanceof ApiError && err.code === 'fs.conflict') error.value = t('files.conflict')
    else error.value = apiError.message(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <EdModal v-model="visible" :title="path ?? ''" size="xl" :static-backdrop="dirty">
    <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
    <div v-if="loading" class="text-center py-5">
      <span class="spinner-border" aria-hidden="true"></span>
    </div>
    <CodeEditor
      v-else-if="path && !error"
      v-model="content"
      :filename="path.split('/').pop()"
      :dark="dark"
      @save="save"
    />
    <template #footer>
      <span v-if="dirty" class="text-warning small me-auto">{{ t('files.unsaved') }}</span>
      <button type="button" class="btn btn-secondary" @click="emit('close')">
        {{ t('common.close') }}
      </button>
      <button type="button" class="btn btn-primary" :disabled="!dirty || saving" @click="save">
        {{ saving ? t('common.saving') : t('common.save') }}
      </button>
    </template>
  </EdModal>
</template>
