<script setup lang="ts">
/** Bootstrap tooltip around the default slot. */
import Tooltip from 'bootstrap/js/dist/tooltip'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{ text: string; placement?: 'top' | 'bottom' | 'start' | 'end' }>(),
  { placement: 'top' },
)

const el = ref<HTMLElement | null>(null)
let instance: Tooltip | null = null

function bsPlacement(): 'top' | 'bottom' | 'left' | 'right' {
  const rtl = document.documentElement.dir === 'rtl'
  if (props.placement === 'start') return rtl ? 'right' : 'left'
  if (props.placement === 'end') return rtl ? 'left' : 'right'
  return props.placement
}

onMounted(() => {
  if (el.value) instance = new Tooltip(el.value, { title: props.text, placement: bsPlacement() })
})

watch(
  () => props.text,
  (text) => instance?.setContent({ '.tooltip-inner': text }),
)

onBeforeUnmount(() => {
  instance?.dispose()
  instance = null
})
</script>

<template>
  <span ref="el" class="d-inline-block" tabindex="0"><slot /></span>
</template>
