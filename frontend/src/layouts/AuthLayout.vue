<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useTheme, type ThemeChoice } from '@/composables/useTheme'
import { applyLocale, LOCALES } from '@/i18n'

const { t, locale } = useI18n()
const { theme, setTheme } = useTheme()

function nextTheme(): void {
  const order: ThemeChoice[] = ['light', 'dark', 'system']
  setTheme(order[(order.indexOf(theme.value) + 1) % order.length] ?? 'system')
}
</script>

<template>
  <div
    class="min-vh-100 d-flex flex-column align-items-center justify-content-center p-3 bg-body-tertiary"
  >
    <div class="ed-auth-card">
      <div class="text-center mb-4">
        <img src="/assets/favicon.svg" width="48" height="48" alt="" />
      </div>
      <router-view />
      <div class="d-flex justify-content-center gap-3 mt-4 small">
        <button
          v-for="code in LOCALES"
          :key="code"
          type="button"
          class="btn btn-link btn-sm p-0"
          :class="{ 'fw-bold': locale === code }"
          @click="applyLocale(code)"
        >
          {{ t(`common.lang_${code}`) }}
        </button>
        <button
          type="button"
          class="btn btn-link btn-sm p-0"
          :aria-label="t('common.theme')"
          @click="nextTheme"
        >
          <i class="bi bi-circle-half" aria-hidden="true"></i> {{ t(`common.theme_${theme}`) }}
        </button>
      </div>
    </div>
  </div>
</template>
