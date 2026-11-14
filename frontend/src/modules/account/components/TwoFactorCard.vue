<script setup lang="ts">
/** TOTP enrollment: QR + manual key → confirm code → recovery codes shown once. */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { authApi, type TotpSetup } from '@/api/client'
import { useApiError } from '@/composables/useApiError'
import { useSudo } from '@/composables/useSudo'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const toast = useToast()
const apiError = useApiError()
const sudo = useSudo()

const setup = ref<TotpSetup | null>(null)
const code = ref('')
const codeError = ref('')
const recoveryCodes = ref<string[]>([])
const busy = ref(false)

async function guarded(action: () => Promise<void>): Promise<void> {
  busy.value = true
  try {
    await sudo.run(action)
  } catch (error) {
    toast.error(apiError.message(error), apiError.requestId(error))
  } finally {
    busy.value = false
  }
}

const start = () =>
  guarded(async () => {
    setup.value = await authApi.totpSetup()
    code.value = ''
    codeError.value = ''
  })

async function activate(): Promise<void> {
  busy.value = true
  codeError.value = ''
  try {
    recoveryCodes.value = (await authApi.totpEnable({ code: code.value })).recovery_codes
    setup.value = null
    await auth.refresh()
    toast.success(t('account.two_factor_enabled'))
  } catch (error) {
    codeError.value = apiError.message(error)
  } finally {
    busy.value = false
  }
}

const disable = () =>
  guarded(async () => {
    await authApi.totpDisable()
    await auth.refresh()
    toast.success(t('account.two_factor_disabled'))
  })

const regenerate = () =>
  guarded(async () => {
    recoveryCodes.value = (await authApi.recoveryCodes()).recovery_codes
  })

async function copyCodes(): Promise<void> {
  await navigator.clipboard.writeText(recoveryCodes.value.join('\n'))
  toast.info(t('common.copied'))
}
</script>

<template>
  <div class="card h-100">
    <div class="card-header fw-semibold">{{ t('account.two_factor') }}</div>
    <div class="card-body">
      <template v-if="recoveryCodes.length">
        <h2 class="h6">{{ t('account.recovery_title') }}</h2>
        <p class="small text-body-secondary">{{ t('account.recovery_text') }}</p>
        <ul class="list-unstyled row row-cols-2 g-1 font-monospace ltr-island mb-3">
          <li v-for="c in recoveryCodes" :key="c" class="col">{{ c }}</li>
        </ul>
        <button type="button" class="btn btn-outline-secondary btn-sm me-2" @click="copyCodes">
          <i class="bi bi-clipboard" aria-hidden="true"></i> {{ t('common.copy') }}
        </button>
        <button type="button" class="btn btn-primary btn-sm" @click="recoveryCodes = []">
          {{ t('account.done_saved_codes') }}
        </button>
      </template>

      <template v-else-if="setup">
        <p class="small">{{ t('account.scan_qr') }}</p>
        <div class="d-flex flex-wrap gap-3 align-items-start">
          <img :src="setup.qr_svg" :alt="t('account.qr_alt')" class="ed-qr" />
          <div class="flex-grow-1">
            <p class="small mb-1">{{ t('account.manual_secret') }}</p>
            <code class="d-block mb-3 user-select-all">{{ setup.secret }}</code>
            <form @submit.prevent="activate">
              <label class="form-label" for="totp-code">{{ t('account.confirm_code') }}</label>
              <input
                id="totp-code"
                v-model.trim="code"
                class="form-control ltr-island mb-2"
                :class="{ 'is-invalid': codeError }"
                inputmode="numeric"
                autocomplete="one-time-code"
                maxlength="6"
                required
              />
              <div v-if="codeError" class="invalid-feedback d-block mb-2">{{ codeError }}</div>
              <button
                type="submit"
                class="btn btn-primary btn-sm me-2"
                :disabled="busy || code.length !== 6"
              >
                {{ t('account.activate') }}
              </button>
              <button type="button" class="btn btn-link btn-sm" @click="setup = null">
                {{ t('common.cancel') }}
              </button>
            </form>
          </div>
        </div>
      </template>

      <template v-else-if="auth.user?.totp_enabled">
        <p>
          <i class="bi bi-shield-check text-success" aria-hidden="true"></i>
          {{ t('account.two_factor_on') }}
        </p>
        <button
          type="button"
          class="btn btn-outline-secondary btn-sm me-2"
          :disabled="busy"
          @click="regenerate"
        >
          {{ t('account.regenerate_codes') }}
        </button>
        <button
          type="button"
          class="btn btn-outline-danger btn-sm"
          :disabled="busy"
          @click="disable"
        >
          {{ t('account.disable_2fa') }}
        </button>
      </template>

      <template v-else>
        <p>
          <i class="bi bi-shield-exclamation text-warning" aria-hidden="true"></i>
          {{ t('account.two_factor_off') }}
        </p>
        <button type="button" class="btn btn-primary btn-sm" :disabled="busy" @click="start">
          {{ t('account.enable_2fa') }}
        </button>
      </template>
    </div>
  </div>
</template>
