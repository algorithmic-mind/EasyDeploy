<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import EdModal from '@/components/ui/EdModal.vue'
import { confirmRequest } from '@/composables/useConfirm'

const { t } = useI18n()
const typed = ref('')

const visible = computed({
  get: () => confirmRequest.value !== null,
  set: (value: boolean) => {
    if (!value) finish(false)
  },
})
const canConfirm = computed(
  () => !confirmRequest.value?.typeToConfirm || typed.value === confirmRequest.value.typeToConfirm,
)

function finish(ok: boolean): void {
  const request = confirmRequest.value
  confirmRequest.value = null
  request?.resolve(ok)
}

watch(visible, () => (typed.value = ''))
</script>

<template>
  <EdModal v-model="visible" :title="confirmRequest?.title ?? ''">
    <p class="mb-2">{{ confirmRequest?.message }}</p>
    <template v-if="confirmRequest?.typeToConfirm">
      <label class="form-label small" for="confirm-type">
        {{ t('common.type_to_confirm', { text: confirmRequest.typeToConfirm }) }}
      </label>
      <input id="confirm-type" v-model="typed" class="form-control ltr-island" autocomplete="off" />
    </template>
    <template #footer>
      <button type="button" class="btn btn-secondary" @click="finish(false)">
        {{ t('common.cancel') }}
      </button>
      <button
        type="button"
        class="btn"
        :class="confirmRequest?.danger ? 'btn-danger' : 'btn-primary'"
        :disabled="!canConfirm"
        @click="finish(true)"
      >
        {{ confirmRequest?.confirmLabel ?? t('common.confirm') }}
      </button>
    </template>
  </EdModal>
</template>
