<script setup lang="ts">
/** Stand-in for menu pages that later roadmap phases deliver (§15). */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'

const route = useRoute()
const { t } = useI18n()
const titleKey = computed(() => String(route.meta.titleKey ?? 'common.under_construction'))
const phase = computed(() => Number(route.meta.phase ?? 0))
</script>

<template>
  <div>
    <h1 class="h4 mb-4">{{ t(titleKey) }}</h1>
    <div class="card">
      <EmptyState
        icon="bi-cone-striped"
        :title="t('common.under_construction')"
        :text="t('common.coming_in_phase', { phase })"
      />
    </div>
  </div>
</template>
