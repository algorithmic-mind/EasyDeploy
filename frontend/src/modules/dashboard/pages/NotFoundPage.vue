<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import EmptyState from '@/components/EmptyState.vue'

const { t } = useI18n()
</script>

<template>
  <div class="card">
    <EmptyState
      icon="bi-signpost-split"
      :title="t('common.not_found_title')"
      :text="t('common.not_found_text')"
    >
      <router-link to="/" class="btn btn-primary btn-sm">{{ t('common.go_home') }}</router-link>
    </EmptyState>
  </div>
</template>
