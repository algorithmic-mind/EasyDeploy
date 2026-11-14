<script setup lang="ts">
/** Bootstrap modal wrapper (v-model controls visibility). */
import Modal from 'bootstrap/js/dist/modal'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    size?: 'sm' | 'lg' | 'xl'
    staticBackdrop?: boolean
  }>(),
  { size: undefined, staticBackdrop: false },
)
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const { t } = useI18n()

const el = ref<HTMLElement | null>(null)
let instance: Modal | null = null

function onHidden(): void {
  emit('update:modelValue', false)
}

onMounted(() => {
  if (!el.value) return
  instance = new Modal(el.value, {
    backdrop: props.staticBackdrop ? 'static' : true,
    keyboard: !props.staticBackdrop,
  })
  el.value.addEventListener('hidden.bs.modal', onHidden)
  if (props.modelValue) instance.show()
})

watch(
  () => props.modelValue,
  (visible) => (visible ? instance?.show() : instance?.hide()),
)

onBeforeUnmount(() => {
  el.value?.removeEventListener('hidden.bs.modal', onHidden)
  instance?.dispose()
  instance = null
})
</script>

<template>
  <div ref="el" class="modal fade" tabindex="-1" aria-hidden="true" :aria-label="title">
    <div class="modal-dialog modal-dialog-centered" :class="size ? `modal-${size}` : ''">
      <div class="modal-content">
        <div class="modal-header">
          <h2 class="modal-title fs-5">{{ title }}</h2>
          <button
            type="button"
            class="btn-close"
            :aria-label="t('common.close')"
            @click="emit('update:modelValue', false)"
          ></button>
        </div>
        <div class="modal-body">
          <slot />
        </div>
        <div v-if="$slots.footer" class="modal-footer">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </div>
</template>
