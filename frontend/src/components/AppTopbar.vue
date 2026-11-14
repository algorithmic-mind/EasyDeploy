<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { authApi } from '@/api/client'
import EdDropdown from '@/components/ui/EdDropdown.vue'
import { useTheme, type ThemeChoice } from '@/composables/useTheme'
import { applyLocale, LOCALES, type Locale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useTasksStore } from '@/stores/tasks'

const emit = defineEmits<{ toggleSidebar: [] }>()
const { t, locale } = useI18n()
const auth = useAuthStore()
const tasks = useTasksStore()
const router = useRouter()
const { theme, setTheme } = useTheme()

const THEMES: { value: ThemeChoice; icon: string }[] = [
  { value: 'light', icon: 'bi-sun' },
  { value: 'dark', icon: 'bi-moon-stars' },
  { value: 'system', icon: 'bi-circle-half' },
]

function changeLocale(value: Locale): void {
  applyLocale(value)
  if (auth.isAuthenticated) void authApi.updateMe({ language: value }).catch(() => undefined)
}

function changeTheme(value: ThemeChoice): void {
  setTheme(value)
  if (auth.isAuthenticated) void authApi.updateMe({ theme: value }).catch(() => undefined)
}

async function signOut(): Promise<void> {
  await auth.logout()
  tasks.stop()
  await router.push({ name: 'login' })
}
</script>

<template>
  <header class="ed-topbar d-flex align-items-center gap-2 px-3">
    <button
      type="button"
      class="btn btn-link text-body d-lg-none px-1"
      :aria-label="t('common.toggle_navigation')"
      @click="emit('toggleSidebar')"
    >
      <i class="bi bi-list fs-4" aria-hidden="true"></i>
    </button>
    <div class="flex-grow-1"></div>

    <button
      type="button"
      class="btn btn-link text-body position-relative"
      :aria-label="t('tasks.open_center')"
      @click="tasks.show()"
    >
      <i class="bi bi-list-task fs-5" aria-hidden="true"></i>
      <span
        v-if="tasks.runningCount > 0"
        class="position-absolute top-0 start-100 translate-middle badge rounded-pill text-bg-primary"
      >
        {{ tasks.runningCount }}
        <span class="visually-hidden">{{
          t('tasks.running_count', { n: tasks.runningCount })
        }}</span>
      </span>
    </button>

    <EdDropdown icon="bi-translate" :label="t('common.language')">
      <li v-for="code in LOCALES" :key="code">
        <button
          type="button"
          class="dropdown-item"
          :class="{ active: locale === code }"
          @click="changeLocale(code)"
        >
          {{ t(`common.lang_${code}`) }}
        </button>
      </li>
    </EdDropdown>

    <EdDropdown icon="bi-circle-half" :label="t('common.theme')">
      <li v-for="item in THEMES" :key="item.value">
        <button
          type="button"
          class="dropdown-item d-flex align-items-center gap-2"
          :class="{ active: theme === item.value }"
          @click="changeTheme(item.value)"
        >
          <i class="bi" :class="item.icon" aria-hidden="true"></i>
          {{ t(`common.theme_${item.value}`) }}
        </button>
      </li>
    </EdDropdown>

    <EdDropdown icon="bi-person-circle" :label="auth.user?.username ?? ''">
      <template #label>
        <span class="d-none d-sm-inline ms-1">{{ auth.user?.username }}</span>
      </template>
      <li>
        <router-link class="dropdown-item" :to="{ name: 'account' }">
          <i class="bi bi-person-gear me-2" aria-hidden="true"></i>{{ t('nav.account') }}
        </router-link>
      </li>
      <li><hr class="dropdown-divider" /></li>
      <li>
        <button type="button" class="dropdown-item text-danger" @click="signOut">
          <i class="bi bi-box-arrow-right me-2 ed-flip-rtl" aria-hidden="true"></i
          >{{ t('auth.sign_out') }}
        </button>
      </li>
    </EdDropdown>
  </header>
</template>
