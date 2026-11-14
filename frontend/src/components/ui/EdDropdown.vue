<script setup lang="ts">
/** Bootstrap dropdown wrapper. Put `<li>` items (dropdown-item buttons/links) in the default slot. */
import Dropdown from 'bootstrap/js/dist/dropdown'
import { onBeforeUnmount, onMounted, ref } from 'vue'

withDefaults(
  defineProps<{ label?: string; icon?: string; btnClass?: string; align?: 'start' | 'end' }>(),
  { label: '', icon: '', btnClass: 'btn btn-link text-body', align: 'end' },
)

const toggle = ref<HTMLButtonElement | null>(null)
let instance: Dropdown | null = null

onMounted(() => {
  if (toggle.value) instance = new Dropdown(toggle.value)
})

onBeforeUnmount(() => {
  instance?.dispose()
  instance = null
})

defineExpose({ hide: () => instance?.hide() })
</script>

<template>
  <div class="dropdown">
    <button
      ref="toggle"
      type="button"
      :class="[btnClass, 'dropdown-toggle']"
      data-bs-toggle="dropdown"
      aria-expanded="false"
      :aria-label="label"
    >
      <i v-if="icon" class="bi" :class="icon" aria-hidden="true"></i>
      <slot name="label" />
    </button>
    <ul class="dropdown-menu shadow-sm" :class="align === 'end' ? 'dropdown-menu-end' : ''">
      <slot />
    </ul>
  </div>
</template>
