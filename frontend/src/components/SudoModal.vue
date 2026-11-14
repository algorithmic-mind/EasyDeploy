<script setup lang="ts">
/** Global re-authentication dialog driven by `useSudo`. */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { authApi } from '@/api/client'
import EdModal from '@/components/ui/EdModal.vue'
import { useApiError } from '@/composables/useApiError'
import { sudoPrompt } from '@/composables/useSudo'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const apiError = useApiError()

const password = ref('')
const code = ref('')
const error = ref('')
const busy = ref(false)
const visible = computed({
  get: () => sudoPrompt.value !== null,
  set: (value: boolean) => {
    if (!value) finish(false)
  },
})

function finish(ok: boolean): void {
  const prompt = sudoPrompt.value
  sudoPrompt.value = null
  prompt?.resolve(ok)
}

watch(visible, (open) => {
  if (open) {
    password.value = ''
    code.value = ''
    error.value = ''
  }
})

async function submit(): Promise<void> {
  busy.value = true
  error.value = ''
  try {
    await authApi.sudo({ password: password.value, code: code.value || undefined })
    await auth.refresh()
    finish(true)
  } catch (err) {
    error.value = apiError.message(err)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <EdModal v-model="visible" :title="t('auth.sudo_title')" size="sm">
    <form id="sudo-form" @submit.prevent="submit">
      <p class="small text-body-secondary">{{ t('auth.sudo_text') }}</p>
      <div v-if="error" class="alert alert-danger py-2 small">{{ error }}</div>
      <label class="form-label" for="sudo-password">{{ t('auth.password') }}</label>
      <input
        id="sudo-password"
        v-model="password"
        type="password"
        class="form-control mb-2"
        autocomplete="current-password"
        required
      />
      <template v-if="auth.user?.totp_enabled">
        <label class="form-label" for="sudo-code">{{ t('auth.code') }}</label>
        <input
          id="sudo-code"
          v-model="code"
          class="form-control ltr-island"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          required
        />
      </template>
    </form>
    <template #footer>
      <button type="button" class="btn btn-secondary" @click="finish(false)">
        {{ t('common.cancel') }}
      </button>
      <button type="submit" form="sudo-form" class="btn btn-primary" :disabled="busy">
        {{ t('auth.sudo_submit') }}
      </button>
    </template>
  </EdModal>
</template>
