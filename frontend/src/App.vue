<script setup lang="ts">
import { watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import EdToastHost from '@/components/ui/EdToastHost.vue'

const { t, locale } = useI18n()
const route = useRoute()

watch(
  () => [route.meta.titleKey, locale.value] as const,
  ([key]) => {
    const app = t('common.app_name')
    document.title = key ? `${t(String(key))} · ${app}` : app
  },
  { immediate: true },
)
</script>

<template>
  <router-view />
  <EdToastHost />
</template>
