<script setup lang="ts">
withDefaults(defineProps<{ icon?: string; title: string; text?: string }>(), {
  icon: 'bi-inbox',
  text: '',
})
</script>

<template>
  <div class="text-center text-body-secondary py-5 px-3">
    <i class="bi fs-1 d-block mb-2" :class="icon" aria-hidden="true"></i>
    <p class="fw-semibold mb-1 text-body">{{ title }}</p>
    <p v-if="text" class="mb-3">{{ text }}</p>
    <slot />
  </div>
</template>
