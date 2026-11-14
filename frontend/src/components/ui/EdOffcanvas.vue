<script setup lang="ts">
/** Bootstrap offcanvas (drawer) wrapper. `placement="end"` is mirrored automatically in RTL. */
import Offcanvas from 'bootstrap/js/dist/offcanvas'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = withDefaults(
  defineProps<{ modelValue: boolean; title: string; placement?: 'start' | 'end' }>(),
  { placement: 'end' },
)
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const { t } = useI18n()

const el = ref<HTMLElement | null>(null)
let instance: Offcanvas | null = null

function onHidden(): void {
  emit('update:modelValue', false)
}

onMounted(() => {
  if (!el.value) return
  instance = new Offcanvas(el.value)
  el.value.addEventListener('hidden.bs.offcanvas', onHidden)
  if (props.modelValue) instance.show()
})

watch(
  () => props.modelValue,
  (visible) => (visible ? instance?.show() : instance?.hide()),
)

onBeforeUnmount(() => {
  el.value?.removeEventListener('hidden.bs.offcanvas', onHidden)
  instance?.dispose()
  instance = null
})
</script>

<template>
  <div
    ref="el"
    class="offcanvas"
    :class="`offcanvas-${placement}`"
    tabindex="-1"
    :aria-label="title"
  >
    <div class="offcanvas-header border-bottom">
      <h2 class="offcanvas-title fs-5">{{ title }}</h2>
      <button
        type="button"
        class="btn-close"
        :aria-label="t('common.close')"
        @click="emit('update:modelValue', false)"
      ></button>
    </div>
    <div class="offcanvas-body">
      <slot />
    </div>
  </div>
</template>
