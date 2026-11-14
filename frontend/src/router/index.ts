import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { onUnauthorized } from '@/api/http'
import PlaceholderPage from '@/components/PlaceholderPage.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { PAGES } from '@/modules/pages'
import { NAVIGATION } from '@/navigation'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    titleKey?: string
    phase?: number
  }
}

const sectionRoutes: RouteRecordRaw[] = NAVIGATION.flatMap((s) =>
  s.pages
    .filter((p) => p.path !== '/')
    .map((p) => ({
      path: p.path.slice(1),
      name: `${s.key}.${p.key}`,
      component: PAGES[p.path] ?? PlaceholderPage,
      meta: { titleKey: `nav.${s.key}.${p.key}`, phase: p.phase },
    })),
)

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    component: AuthLayout,
    meta: { public: true },
    children: [
      {
        path: '',
        name: 'login',
        component: () => import('@/modules/auth/pages/LoginPage.vue'),
        meta: { public: true, titleKey: 'auth.sign_in' },
      },
    ],
  },
  {
    path: '/',
    component: MainLayout,
    children: [
      {
        path: '',
        name: 'overview',
        component: () => import('@/modules/dashboard/pages/OverviewPage.vue'),
        meta: { titleKey: 'nav.overview.title' },
      },
      {
        path: 'account',
        name: 'account',
        component: () => import('@/modules/account/pages/AccountPage.vue'),
        meta: { titleKey: 'nav.account' },
      },
      ...sectionRoutes,
      {
        path: ':pathMatch(.*)*',
        name: 'not-found',
        component: () => import('@/modules/dashboard/pages/NotFoundPage.vue'),
        meta: { titleKey: 'common.not_found_title' },
      },
    ],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.bootstrap()
  if (to.meta.public) {
    return auth.isAuthenticated && to.name === 'login' ? { name: 'overview' } : true
  }
  if (!auth.isAuthenticated) {
    return { name: 'login', query: to.fullPath !== '/' ? { next: to.fullPath } : {} }
  }
  if (auth.mustEnroll2fa && to.name !== 'account') return { name: 'account' }
  return true
})

onUnauthorized(() => {
  const auth = useAuthStore()
  if (!auth.isAuthenticated) return
  auth.clearSession()
  void router.push({ name: 'login', query: { expired: '1' } })
})
