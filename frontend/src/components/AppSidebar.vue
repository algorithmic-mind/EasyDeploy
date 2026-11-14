<script setup lang="ts">
/** Main menu (§2.3). Sections expand/collapse; the section of the current route opens itself. */
import { reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { NAVIGATION } from '@/navigation'

const emit = defineEmits<{ navigate: [] }>()
const { t } = useI18n()
const route = useRoute()

const expanded = reactive<Record<string, boolean>>({})

watch(
  () => route.path,
  (path) => {
    for (const s of NAVIGATION) {
      if (s.pages.some((p) => p.path === path)) expanded[s.key] = true
    }
  },
  { immediate: true },
)
</script>

<template>
  <nav :aria-label="t('common.main_navigation')" class="py-2">
    <template v-for="s in NAVIGATION" :key="s.key">
      <router-link
        v-if="s.pages.length === 1 && s.pages[0]"
        :to="s.pages[0].path"
        class="ed-nav-link ps-3 py-2 d-flex align-items-center gap-2"
        @click="emit('navigate')"
      >
        <i class="bi" :class="s.icon" aria-hidden="true"></i>
        {{ t(`nav.${s.key}.title`) }}
      </router-link>
      <div v-else class="ed-nav-section">
        <button
          type="button"
          :aria-expanded="expanded[s.key] ? 'true' : 'false'"
          :aria-controls="`nav-${s.key}`"
          @click="expanded[s.key] = !expanded[s.key]"
        >
          <i class="bi" :class="s.icon" aria-hidden="true"></i>
          <span>{{ t(`nav.${s.key}.title`) }}</span>
          <i class="bi bi-chevron-right ed-chevron small" aria-hidden="true"></i>
        </button>
        <div v-show="expanded[s.key]" :id="`nav-${s.key}`">
          <router-link
            v-for="p in s.pages"
            :key="p.key"
            :to="p.path"
            class="ed-nav-link"
            @click="emit('navigate')"
          >
            {{ t(`nav.${s.key}.${p.key}`) }}
          </router-link>
        </div>
      </div>
    </template>
  </nav>
</template>
