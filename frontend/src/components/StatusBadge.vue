<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { TaskStatus } from '@/api/client'

const props = defineProps<{ status: TaskStatus }>()
const { t } = useI18n()

const VARIANTS: Record<TaskStatus, string> = {
  pending: 'secondary',
  running: 'primary',
  succeeded: 'success',
  failed: 'danger',
  cancelled: 'warning',
}

const variant = computed(() => VARIANTS[props.status])
</script>

<template>
  <span class="badge rounded-pill" :class="`text-bg-${variant}`">
    <span
      v-if="status === 'running'"
      class="spinner-border spinner-border-sm me-1"
      style="width: 0.6rem; height: 0.6rem"
      aria-hidden="true"
    ></span>
    {{ t(`tasks.status.${status}`) }}
  </span>
</template>
