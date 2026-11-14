import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { authApi, panelApi, type Me, type PanelInfo, type User } from '@/api/client'
import { ApiError } from '@/api/http'
import { applyLocale, isLocale } from '@/i18n'
import { useTheme } from '@/composables/useTheme'

export const useAuthStore = defineStore('auth', () => {
  const me = ref<Me | null>(null)
  const panel = ref<PanelInfo | null>(null)
  const ready = ref(false)
  const pendingSecondFactor = ref(false)

  const user = computed<User | null>(() => me.value?.user ?? null)
  const isAuthenticated = computed(() => user.value !== null)
  const mustEnroll2fa = computed(() => me.value?.must_enroll_2fa ?? false)

  function applyPreferences(u: User): void {
    if (u.language && isLocale(u.language)) applyLocale(u.language)
    if (u.theme) useTheme().setTheme(u.theme)
  }

  /** First call of the app: CSRF cookie, panel branding, current session. */
  async function bootstrap(): Promise<void> {
    if (ready.value) return
    try {
      await authApi.csrf()
      panel.value = await panelApi.info()
      await refresh()
    } finally {
      ready.value = true
    }
  }

  async function refresh(): Promise<void> {
    try {
      me.value = await authApi.me()
      applyPreferences(me.value.user)
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        me.value = null
        return
      }
      throw error
    }
  }

  async function login(username: string, password: string): Promise<'ok' | '2fa_required'> {
    const result = await authApi.login({ username, password })
    if (result.status === '2fa_required') {
      pendingSecondFactor.value = true
      return result.status
    }
    pendingSecondFactor.value = false
    await refresh()
    return 'ok'
  }

  async function verifySecondFactor(input: { code?: string; recovery_code?: string }) {
    await authApi.secondFactor(input)
    pendingSecondFactor.value = false
    await refresh()
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } finally {
      me.value = null
      await authApi.csrf().catch(() => undefined)
    }
  }

  function clearSession(): void {
    me.value = null
  }

  return {
    me,
    panel,
    ready,
    user,
    isAuthenticated,
    mustEnroll2fa,
    pendingSecondFactor,
    bootstrap,
    refresh,
    login,
    verifySecondFactor,
    logout,
    clearSession,
  }
})
