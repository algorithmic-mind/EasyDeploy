/**
 * Navigation paths that have a real page. Everything else in `navigation.ts` renders the
 * phase placeholder. Add an entry here when a module's page is built.
 */
import type { Component } from 'vue'

export const PAGES: Record<string, () => Promise<Component>> = {
  '/host/monitoring': () => import('@/modules/host/pages/MonitoringPage.vue'),
}
