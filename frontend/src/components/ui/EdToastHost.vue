<script setup lang="ts">
/** Renders the global toast queue (`useToast`) with Bootstrap toasts. */
import Toast from 'bootstrap/js/dist/toast'
import { nextTick, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'

import { dismissToast, toasts } from '@/composables/useToast'

const { t } = useI18n()
const instances = new Map<number, Toast>()

function mount(el: Element | null, id: number): void {
  if (!(el instanceof HTMLElement) || instances.has(id)) return
  const toast = new Toast(el, { delay: 6000 })
  el.addEventListener('hidden.bs.toast', () => {
    toast.dispose()
    instances.delete(id)
    dismissToast(id)
  })
  instances.set(id, toast)
  void nextTick(() => toast.show())
}

onBeforeUnmount(() => {
  instances.forEach((toast) => toast.dispose())
  instances.clear()
})
</script>

<template>
  <div class="toast-container position-fixed bottom-0 end-0 p-3" aria-live="polite">
    <div
      v-for="toast in toasts"
      :key="toast.id"
      :ref="(el) => mount(el as Element | null, toast.id)"
      class="toast align-items-center border-0"
      :class="`text-bg-${toast.variant}`"
      role="status"
      aria-atomic="true"
    >
      <div class="d-flex">
        <div class="toast-body">
          <div>{{ toast.text }}</div>
          <small v-if="toast.detail" class="opacity-75 ltr-island">{{ toast.detail }}</small>
        </div>
        <button
          type="button"
          class="btn-close btn-close-white me-2 m-auto"
          data-bs-dismiss="toast"
          :aria-label="t('common.close')"
        ></button>
      </div>
    </div>
  </div>
</template>
