<script setup lang="ts">
/** Sign in, then (when enabled) the TOTP / recovery-code step (§9.1). */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/http'
import { useApiError } from '@/composables/useApiError'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const apiError = useApiError()

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const code = ref('')
const useRecovery = ref(false)
const busy = ref(false)
const error = ref('')
const step = computed(() => (auth.pendingSecondFactor ? 'second' : 'password'))
const panelName = computed(() => auth.panel?.name ?? t('common.app_name'))
const expired = computed(() => route.query.expired === '1')

function describe(err: unknown): string {
  if (err instanceof ApiError && err.code === 'auth.locked') {
    return t('auth.locked', { seconds: Number(err.details.retry_after ?? 60) })
  }
  return apiError.message(err)
}

async function goNext(): Promise<void> {
  const target = typeof route.query.next === 'string' ? route.query.next : '/'
  await router.replace(target.startsWith('/') && !target.startsWith('//') ? target : '/')
}

async function submitPassword(): Promise<void> {
  busy.value = true
  error.value = ''
  try {
    const status = await auth.login(username.value, password.value)
    password.value = ''
    if (status === 'ok') await goNext()
  } catch (err) {
    error.value = describe(err)
  } finally {
    busy.value = false
  }
}

async function submitCode(): Promise<void> {
  busy.value = true
  error.value = ''
  try {
    await auth.verifySecondFactor(
      useRecovery.value ? { recovery_code: code.value } : { code: code.value },
    )
    await goNext()
  } catch (err) {
    error.value = describe(err)
    code.value = ''
  } finally {
    busy.value = false
  }
}

function backToPassword(): void {
  auth.pendingSecondFactor = false
  code.value = ''
  error.value = ''
}
</script>

<template>
  <div class="card shadow-sm">
    <div class="card-body p-4">
      <template v-if="step === 'password'">
        <h1 class="h4 mb-3 text-center">{{ t('auth.sign_in_title', { name: panelName }) }}</h1>
        <div v-if="expired && !error" class="alert alert-info py-2 small">
          {{ t('auth.session_expired') }}
        </div>
        <div v-if="error" class="alert alert-danger py-2 small" role="alert">{{ error }}</div>
        <form novalidate @submit.prevent="submitPassword">
          <div class="mb-3">
            <label class="form-label" for="username">{{ t('auth.username') }}</label>
            <input
              id="username"
              v-model.trim="username"
              class="form-control"
              autocomplete="username"
              autocapitalize="none"
              spellcheck="false"
              dir="ltr"
              required
              autofocus
            />
          </div>
          <div class="mb-3">
            <label class="form-label" for="password">{{ t('auth.password') }}</label>
            <div class="input-group">
              <input
                id="password"
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                class="form-control"
                autocomplete="current-password"
                dir="ltr"
                required
              />
              <button
                type="button"
                class="btn btn-outline-secondary"
                :aria-label="showPassword ? t('auth.hide_password') : t('auth.show_password')"
                @click="showPassword = !showPassword"
              >
                <i
                  class="bi"
                  :class="showPassword ? 'bi-eye-slash' : 'bi-eye'"
                  aria-hidden="true"
                ></i>
              </button>
            </div>
          </div>
          <button
            type="submit"
            class="btn btn-primary w-100"
            :disabled="busy || !username || !password"
          >
            <span
              v-if="busy"
              class="spinner-border spinner-border-sm me-2"
              aria-hidden="true"
            ></span>
            {{ busy ? t('auth.signing_in') : t('auth.sign_in') }}
          </button>
        </form>
      </template>

      <template v-else>
        <h1 class="h4 mb-2 text-center">{{ t('auth.two_factor_title') }}</h1>
        <p class="text-body-secondary small text-center">
          {{ useRecovery ? t('auth.recovery_text') : t('auth.two_factor_text') }}
        </p>
        <div v-if="error" class="alert alert-danger py-2 small" role="alert">{{ error }}</div>
        <form novalidate @submit.prevent="submitCode">
          <label class="form-label" for="otp">
            {{ useRecovery ? t('auth.recovery_code') : t('auth.code') }}
          </label>
          <input
            id="otp"
            v-model.trim="code"
            class="form-control form-control-lg text-center mb-3 ltr-island"
            :inputmode="useRecovery ? 'text' : 'numeric'"
            autocomplete="one-time-code"
            :maxlength="useRecovery ? 11 : 6"
            required
            autofocus
          />
          <button type="submit" class="btn btn-primary w-100" :disabled="busy || !code">
            {{ t('auth.verify') }}
          </button>
        </form>
        <div class="d-flex justify-content-between mt-3 small">
          <button type="button" class="btn btn-link btn-sm p-0" @click="useRecovery = !useRecovery">
            {{ useRecovery ? t('auth.use_code') : t('auth.use_recovery') }}
          </button>
          <button type="button" class="btn btn-link btn-sm p-0" @click="backToPassword">
            {{ t('auth.back_to_sign_in') }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
