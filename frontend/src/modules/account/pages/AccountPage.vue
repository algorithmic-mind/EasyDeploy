<script setup lang="ts">
/** Account: preferences, password change, TOTP enrollment (§9.1). */
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import TwoFactorCard from '@/modules/account/components/TwoFactorCard.vue'
import { authApi } from '@/api/client'
import { ApiError } from '@/api/http'
import { useApiError } from '@/composables/useApiError'
import { useTheme } from '@/composables/useTheme'
import { useToast } from '@/composables/useToast'
import { applyLocale, isLocale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const toast = useToast()
const apiError = useApiError()
const { setTheme } = useTheme()

const prefs = reactive({
  language: auth.user?.language ?? 'en',
  theme: auth.user?.theme ?? 'system',
  calendar: auth.user?.calendar ?? 'gregorian',
  timezone: auth.user?.timezone ?? 'UTC',
})
const savingPrefs = ref(false)
const prefErrors = ref<Record<string, string[]>>({})

const timezones = computed<string[]>(() => {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] }
  const zones = intl.supportedValuesOf?.('timeZone') ?? []
  return zones.includes('UTC') ? zones : ['UTC', ...zones]
})

async function savePreferences(): Promise<void> {
  savingPrefs.value = true
  prefErrors.value = {}
  try {
    await authApi.updateMe({ ...prefs })
    await auth.refresh()
    if (isLocale(prefs.language)) applyLocale(prefs.language)
    setTheme(prefs.theme)
    toast.success(t('common.saved'))
  } catch (error) {
    if (error instanceof ApiError) prefErrors.value = error.fieldErrors()
    toast.error(apiError.message(error))
  } finally {
    savingPrefs.value = false
  }
}

const pwd = reactive({ current: '', next: '', confirm: '' })
const pwdErrors = ref<Record<string, string[]>>({})
const savingPwd = ref(false)

async function changePassword(): Promise<void> {
  pwdErrors.value = {}
  if (pwd.next !== pwd.confirm) {
    pwdErrors.value = { confirm: [t('account.password_mismatch')] }
    return
  }
  savingPwd.value = true
  try {
    await authApi.changePassword({ current_password: pwd.current, new_password: pwd.next })
    pwd.current = pwd.next = pwd.confirm = ''
    toast.success(t('account.password_changed'))
  } catch (error) {
    if (error instanceof ApiError) pwdErrors.value = error.fieldErrors()
    else toast.error(apiError.message(error))
  } finally {
    savingPwd.value = false
  }
}
</script>

<template>
  <div>
    <h1 class="h4 mb-4">{{ t('account.title') }}</h1>
    <div v-if="auth.mustEnroll2fa" class="alert alert-warning">
      {{ t('account.two_factor_required') }}
    </div>

    <div class="row g-3">
      <div class="col-12 col-lg-6">
        <TwoFactorCard />
      </div>

      <div class="col-12 col-lg-6">
        <form class="card" @submit.prevent="savePreferences">
          <div class="card-header fw-semibold">{{ t('account.profile') }}</div>
          <div class="card-body row g-3">
            <div class="col-sm-6">
              <label class="form-label" for="pref-lang">{{ t('common.language') }}</label>
              <select id="pref-lang" v-model="prefs.language" class="form-select">
                <option value="en">{{ t('common.lang_en') }}</option>
                <option value="fa">{{ t('common.lang_fa') }}</option>
              </select>
            </div>
            <div class="col-sm-6">
              <label class="form-label" for="pref-theme">{{ t('common.theme') }}</label>
              <select id="pref-theme" v-model="prefs.theme" class="form-select">
                <option value="system">{{ t('common.theme_system') }}</option>
                <option value="light">{{ t('common.theme_light') }}</option>
                <option value="dark">{{ t('common.theme_dark') }}</option>
              </select>
            </div>
            <div class="col-sm-6">
              <label class="form-label" for="pref-cal">{{ t('account.calendar') }}</label>
              <select id="pref-cal" v-model="prefs.calendar" class="form-select">
                <option value="gregorian">{{ t('account.calendar_gregorian') }}</option>
                <option value="jalali">{{ t('account.calendar_jalali') }}</option>
              </select>
            </div>
            <div class="col-sm-6">
              <label class="form-label" for="pref-tz">{{ t('account.timezone') }}</label>
              <select
                id="pref-tz"
                v-model="prefs.timezone"
                class="form-select ltr-island"
                :class="{ 'is-invalid': prefErrors.timezone }"
              >
                <option v-for="zone in timezones" :key="zone" :value="zone">{{ zone }}</option>
              </select>
              <div v-for="msg in prefErrors.timezone" :key="msg" class="invalid-feedback">
                {{ msg }}
              </div>
            </div>
          </div>
          <div class="card-footer text-end">
            <button type="submit" class="btn btn-primary" :disabled="savingPrefs">
              {{ savingPrefs ? t('common.saving') : t('common.save') }}
            </button>
          </div>
        </form>

        <form class="card mt-3" @submit.prevent="changePassword">
          <div class="card-header fw-semibold">{{ t('account.password_section') }}</div>
          <div class="card-body">
            <div class="mb-3">
              <label class="form-label" for="pwd-current">{{
                t('account.current_password')
              }}</label>
              <input
                id="pwd-current"
                v-model="pwd.current"
                type="password"
                class="form-control"
                dir="ltr"
                autocomplete="current-password"
                :class="{ 'is-invalid': pwdErrors.current_password }"
                required
              />
              <div v-for="msg in pwdErrors.current_password" :key="msg" class="invalid-feedback">
                {{ msg }}
              </div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="pwd-new">{{ t('account.new_password') }}</label>
              <input
                id="pwd-new"
                v-model="pwd.next"
                type="password"
                class="form-control"
                dir="ltr"
                autocomplete="new-password"
                minlength="12"
                :class="{ 'is-invalid': pwdErrors.new_password }"
                aria-describedby="pwd-help"
                required
              />
              <div id="pwd-help" class="form-text">{{ t('account.password_help') }}</div>
              <div v-for="msg in pwdErrors.new_password" :key="msg" class="invalid-feedback">
                {{ msg }}
              </div>
            </div>
            <div>
              <label class="form-label" for="pwd-confirm">{{
                t('account.confirm_password')
              }}</label>
              <input
                id="pwd-confirm"
                v-model="pwd.confirm"
                type="password"
                class="form-control"
                dir="ltr"
                autocomplete="new-password"
                :class="{ 'is-invalid': pwdErrors.confirm }"
                required
              />
              <div v-for="msg in pwdErrors.confirm" :key="msg" class="invalid-feedback">
                {{ msg }}
              </div>
            </div>
          </div>
          <div class="card-footer text-end">
            <button type="submit" class="btn btn-primary" :disabled="savingPwd">
              {{ t('account.change_password') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
