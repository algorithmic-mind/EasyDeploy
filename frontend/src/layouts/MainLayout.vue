<script setup lang="ts">
import Offcanvas from 'bootstrap/js/dist/offcanvas'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import AppSidebar from '@/components/AppSidebar.vue'
import AppTopbar from '@/components/AppTopbar.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import SudoModal from '@/components/SudoModal.vue'
import TaskCenter from '@/components/TaskCenter.vue'
import { useTasksStore } from '@/stores/tasks'

const { t } = useI18n()
const tasks = useTasksStore()

// Mobile sidebar: a Bootstrap offcanvas (wrapped here because it shares the sidebar markup).
const mobileNav = ref<HTMLElement | null>(null)
let offcanvas: Offcanvas | null = null

onMounted(() => {
  if (mobileNav.value) offcanvas = new Offcanvas(mobileNav.value)
  void tasks.start()
})

onBeforeUnmount(() => {
  offcanvas?.dispose()
  tasks.stop()
})
</script>

<template>
  <a class="visually-hidden-focusable position-absolute p-2" href="#main">{{
    t('common.skip_to_content')
  }}</a>
  <div class="ed-shell d-flex">
    <aside class="ed-sidebar ed-sidebar-desktop d-none d-lg-block">
      <div class="ed-brand">
        <img src="/assets/favicon.svg" width="24" height="24" alt="" />
        <span>{{ t('common.app_name') }}</span>
      </div>
      <AppSidebar />
    </aside>

    <div
      ref="mobileNav"
      class="offcanvas offcanvas-start ed-sidebar d-lg-none"
      tabindex="-1"
      :aria-label="t('common.main_navigation')"
    >
      <div class="ed-brand">
        <img src="/assets/favicon.svg" width="24" height="24" alt="" />
        <span class="flex-grow-1">{{ t('common.app_name') }}</span>
        <button
          type="button"
          class="btn-close"
          :aria-label="t('common.close')"
          @click="offcanvas?.hide()"
        ></button>
      </div>
      <div class="overflow-auto">
        <AppSidebar @navigate="offcanvas?.hide()" />
      </div>
    </div>

    <div class="ed-main flex-grow-1 d-flex flex-column">
      <AppTopbar @toggle-sidebar="offcanvas?.toggle()" />
      <main id="main" class="flex-grow-1 p-3 p-md-4">
        <router-view />
      </main>
    </div>
  </div>
  <TaskCenter />
  <SudoModal />
  <ConfirmDialog />
</template>
