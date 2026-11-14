/**
 * Navigation paths that have a real page. Everything else in `navigation.ts` renders the
 * phase placeholder. Add an entry here when a module's page is built.
 */
import type { Component } from 'vue'

export const PAGES: Record<string, () => Promise<Component>> = {
  '/host/monitoring': () => import('@/modules/host/pages/MonitoringPage.vue'),
  '/host/processes': () => import('@/modules/host/pages/ProcessesPage.vue'),
  '/host/services': () => import('@/modules/host/pages/ServicesPage.vue'),
  '/logs/audit': () => import('@/modules/logs/pages/AuditLogPage.vue'),
  '/logs/login': () => import('@/modules/logs/pages/AuditLogPage.vue'),
  '/logs/tasks': () => import('@/modules/logs/pages/TaskLogPage.vue'),
  '/logs/system': () => import('@/modules/logs/pages/SystemLogsPage.vue'),
}
