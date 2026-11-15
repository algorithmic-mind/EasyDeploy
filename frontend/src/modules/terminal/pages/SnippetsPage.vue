<script setup lang="ts">
/** Terminal → Snippets: saved commands for the terminal (§9.10). */
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { terminalApi, type Snippet } from '@/api/client'
import { ApiError } from '@/api/http'
import EmptyState from '@/components/EmptyState.vue'
import EdModal from '@/components/ui/EdModal.vue'
import { useApiError } from '@/composables/useApiError'
import { useConfirm } from '@/composables/useConfirm'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const toast = useToast()
const apiError = useApiError()
const confirm = useConfirm()

const snippets = ref<Snippet[]>([])
const query = ref('')
const loading = ref(false)
const editing = ref<Snippet | null>(null)
const formOpen = ref(false)
const saving = ref(false)
const form = reactive({ name: '', command: '', description: '' })
const fieldErrors = ref<Record<string, string[]>>({})

const valid = computed(() => form.name.trim() !== '' && form.command.trim() !== '')

async function load(): Promise<void> {
  loading.value = true
  try {
    snippets.value = (await terminalApi.snippets({ search: query.value })).results
  } catch (error) {
    toast.error(apiError.message(error))
  } finally {
    loading.value = false
  }
}

function open(snippet: Snippet | null): void {
  editing.value = snippet
  form.name = snippet?.name ?? ''
  form.command = snippet?.command ?? ''
  form.description = snippet?.description ?? ''
  fieldErrors.value = {}
  formOpen.value = true
}

async function save(): Promise<void> {
  if (!valid.value || saving.value) return
  saving.value = true
  try {
    const body = { name: form.name.trim(), command: form.command, description: form.description }
    if (editing.value) await terminalApi.updateSnippet(editing.value.id, body)
    else await terminalApi.createSnippet(body)
    formOpen.value = false
    toast.success(t('common.saved'))
    await load()
  } catch (error) {
    if (error instanceof ApiError) fieldErrors.value = error.fieldErrors()
    toast.error(apiError.message(error))
  } finally {
    saving.value = false
  }
}

async function remove(snippet: Snippet): Promise<void> {
  const ok = await confirm({
    title: t('terminal.delete_snippet'),
    message: t('terminal.delete_confirm', { name: snippet.name }),
    danger: true,
    confirmLabel: t('terminal.delete_snippet'),
  })
  if (!ok) return
  try {
    await terminalApi.deleteSnippet(snippet.id)
    await load()
  } catch (error) {
    toast.error(apiError.message(error))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <h1 class="h4 mb-0 flex-grow-1">{{ t('nav.terminal.snippets') }}</h1>
      <input
        v-model="query"
        type="search"
        class="form-control form-control-sm w-auto"
        :placeholder="t('terminal.search')"
        :aria-label="t('terminal.search')"
        @keyup.enter="load"
        @search="load"
      />
      <button type="button" class="btn btn-sm btn-primary" @click="open(null)">
        <i class="bi bi-plus-lg me-1" aria-hidden="true"></i>{{ t('terminal.add_snippet') }}
      </button>
    </div>

    <div class="card">
      <EmptyState
        v-if="!loading && snippets.length === 0"
        icon="bi-code-square"
        :title="t('terminal.no_snippets')"
        :text="t('terminal.snippets_hint')"
      />
      <div v-else class="table-responsive">
        <table class="table table-sm align-middle mb-0">
          <thead>
            <tr>
              <th>{{ t('terminal.name') }}</th>
              <th>{{ t('terminal.command') }}</th>
              <th>{{ t('terminal.description') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="snippet in snippets" :key="snippet.id">
              <td class="fw-semibold">{{ snippet.name }}</td>
              <td>
                <code class="d-inline-block text-truncate ed-command" dir="ltr">{{
                  snippet.command
                }}</code>
              </td>
              <td class="small text-body-secondary">{{ snippet.description }}</td>
              <td class="text-end text-nowrap">
                <button
                  type="button"
                  class="btn btn-sm btn-link"
                  :aria-label="t('terminal.edit_snippet')"
                  :title="t('terminal.edit_snippet')"
                  @click="open(snippet)"
                >
                  <i class="bi bi-pencil" aria-hidden="true"></i>
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-link text-danger"
                  :aria-label="t('terminal.delete_snippet')"
                  :title="t('terminal.delete_snippet')"
                  @click="remove(snippet)"
                >
                  <i class="bi bi-trash" aria-hidden="true"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <EdModal
      v-model="formOpen"
      :title="editing ? t('terminal.edit_snippet') : t('terminal.add_snippet')"
      size="lg"
    >
      <form id="snippet-form" @submit.prevent="save">
        <div class="mb-3">
          <label class="form-label" for="snippet-name">{{ t('terminal.name') }}</label>
          <input
            id="snippet-name"
            v-model="form.name"
            class="form-control"
            maxlength="100"
            :class="{ 'is-invalid': fieldErrors.name }"
          />
          <div v-for="msg in fieldErrors.name ?? []" :key="msg" class="invalid-feedback">
            {{ msg }}
          </div>
        </div>
        <div class="mb-3">
          <label class="form-label" for="snippet-command">{{ t('terminal.command') }}</label>
          <textarea
            id="snippet-command"
            v-model="form.command"
            class="form-control font-monospace"
            dir="ltr"
            rows="6"
            maxlength="10000"
            spellcheck="false"
            :class="{ 'is-invalid': fieldErrors.command }"
          ></textarea>
          <div v-for="msg in fieldErrors.command ?? []" :key="msg" class="invalid-feedback">
            {{ msg }}
          </div>
        </div>
        <div class="mb-1">
          <label class="form-label" for="snippet-description">{{
            t('terminal.description')
          }}</label>
          <input
            id="snippet-description"
            v-model="form.description"
            class="form-control"
            maxlength="300"
          />
        </div>
      </form>
      <template #footer>
        <button type="button" class="btn btn-secondary" @click="formOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button
          type="submit"
          form="snippet-form"
          class="btn btn-primary"
          :disabled="!valid || saving"
        >
          {{ saving ? t('common.saving') : t('common.save') }}
        </button>
      </template>
    </EdModal>
  </div>
</template>

<style scoped>
.ed-command {
  max-inline-size: 28rem;
}
</style>
