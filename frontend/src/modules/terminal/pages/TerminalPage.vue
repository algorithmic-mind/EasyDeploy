<script setup lang="ts">
/**
 * Terminal → Local / Container exec (§9.10): tabs of xterm sessions and the snippets panel.
 * Opening or reconnecting a tab first confirms sudo mode (`POST /terminal/check`).
 * `?container=<name>` opens the new-tab form for that container (used by the Containers page).
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { terminalApi, type Snippet } from '@/api/client'
import EmptyState from '@/components/EmptyState.vue'
import EdModal from '@/components/ui/EdModal.vue'
import { useApiError } from '@/composables/useApiError'
import { useSudo } from '@/composables/useSudo'
import { useToast } from '@/composables/useToast'
import TerminalView from '@/modules/terminal/components/TerminalView.vue'
import {
  DOCKER_NAME,
  errorKey,
  LINUX_USER,
  newSessionId,
  SHELLS,
  type StatusDetail,
  type TerminalStatus,
  type TerminalTarget,
} from '@/modules/terminal/types'

interface Tab {
  id: string
  title: string
  target: TerminalTarget
  status: TerminalStatus
  detail: StatusDetail
}

type View = InstanceType<typeof TerminalView>

const FONT_KEY = 'ed.terminal.font'
const { t } = useI18n()
const route = useRoute()
const sudo = useSudo()
const toast = useToast()
const apiError = useApiError()

const containerRoute = computed(() => route.path === '/terminal/container-exec')
const tabs = ref<Tab[]>([])
const activeId = ref<string | null>(null)
const views = new Map<string, View>()
const fontSize = ref(readFont())
const formOpen = ref(false)
const form = reactive<TerminalTarget>({
  mode: 'host',
  user: 'root',
  container: '',
  shell_path: '/bin/bash',
})
const snippets = ref<Snippet[]>([])
const snippetQuery = ref('')

const activeTab = computed(() => tabs.value.find((tab) => tab.id === activeId.value) ?? null)
const formValid = computed(() =>
  form.mode === 'host' ? LINUX_USER.test(form.user) : DOCKER_NAME.test(form.container ?? ''),
)
const filteredSnippets = computed(() => {
  const q = snippetQuery.value.trim().toLowerCase()
  if (!q) return snippets.value
  return snippets.value.filter((s) =>
    [s.name, s.command, s.description ?? ''].some((v) => v.toLowerCase().includes(q)),
  )
})

function readFont(): number {
  try {
    const value = Number(localStorage.getItem(FONT_KEY))
    if (value >= 10 && value <= 24) return value
  } catch {
    // storage unavailable
  }
  return 14
}

function setFont(delta: number): void {
  fontSize.value = Math.min(24, Math.max(10, fontSize.value + delta))
  try {
    localStorage.setItem(FONT_KEY, String(fontSize.value))
  } catch {
    // storage unavailable
  }
}

function setView(id: string, view: unknown): void {
  if (view) views.set(id, view as View)
  else views.delete(id)
}

function showForm(container?: string): void {
  form.mode = container || containerRoute.value ? 'container' : 'host'
  form.container = container ?? form.container
  form.shell_path = form.mode === 'container' ? '/bin/sh' : '/bin/bash'
  formOpen.value = true
}

/** Sudo mode is checked by the API first, so an expired sudo shows the password prompt. */
async function confirmSudo(): Promise<boolean> {
  try {
    return (await sudo.run(() => terminalApi.check())) !== undefined
  } catch (error) {
    toast.error(apiError.message(error))
    return false
  }
}

async function openTab(): Promise<void> {
  if (!formValid.value) return
  formOpen.value = false
  if (!(await confirmSudo())) return
  const target: TerminalTarget = {
    mode: form.mode,
    user: form.mode === 'host' ? form.user : 'root',
    container: form.mode === 'container' ? form.container : null,
    shell_path: form.shell_path,
  }
  const index = tabs.value.length + 1
  const title =
    target.mode === 'host' ? `${index} · ${target.user}` : `${index} · ${target.container}`
  const tab: Tab = { id: newSessionId(), title, target, status: 'connecting', detail: {} }
  tabs.value.push(tab)
  activeId.value = tab.id
}

function closeTab(id: string): void {
  const index = tabs.value.findIndex((tab) => tab.id === id)
  if (index < 0) return
  tabs.value.splice(index, 1)
  if (activeId.value === id) activeId.value = tabs.value[Math.max(0, index - 1)]?.id ?? null
}

async function reconnect(tab: Tab): Promise<void> {
  if (!(await confirmSudo())) return
  views.get(tab.id)?.reconnect()
}

function onStatus(tab: Tab, status: TerminalStatus, detail: StatusDetail): void {
  tab.status = status
  tab.detail = detail
}

function statusText(tab: Tab): string {
  if (tab.status === 'exited') return t('terminal.status.exited', { code: tab.detail.code ?? 0 })
  if (tab.status === 'error') {
    return t(`terminal.errors.${errorKey(tab.detail.code)}`, {
      fields: (tab.detail.fields ?? []).join(', '),
    })
  }
  return t(`terminal.status.${tab.status}`)
}

const BADGE: Record<TerminalStatus, string> = {
  connecting: 'text-bg-secondary',
  open: 'text-bg-success',
  exited: 'text-bg-secondary',
  closed: 'text-bg-warning',
  error: 'text-bg-danger',
}

function sendSnippet(snippet: Snippet, run: boolean): void {
  const view = activeId.value ? views.get(activeId.value) : undefined
  if (!view) return
  if (run) view.run(snippet.command)
  else view.insert(snippet.command)
}

async function loadSnippets(): Promise<void> {
  try {
    snippets.value = (await terminalApi.snippets()).results
  } catch {
    snippets.value = []
  }
}

onMounted(() => {
  void loadSnippets()
  const container = typeof route.query.container === 'string' ? route.query.container : ''
  if (container && DOCKER_NAME.test(container)) showForm(container)
})
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <h1 class="h4 mb-0 flex-grow-1">
        {{ containerRoute ? t('nav.terminal.container_exec') : t('nav.terminal.local') }}
      </h1>
      <div class="btn-group btn-group-sm" role="group" :aria-label="t('terminal.font_size')">
        <button
          type="button"
          class="btn btn-outline-secondary"
          :title="t('terminal.smaller')"
          :aria-label="t('terminal.smaller')"
          @click="setFont(-1)"
        >
          <i class="bi bi-dash" aria-hidden="true"></i>
        </button>
        <span class="btn btn-outline-secondary disabled">{{ fontSize }}</span>
        <button
          type="button"
          class="btn btn-outline-secondary"
          :title="t('terminal.larger')"
          :aria-label="t('terminal.larger')"
          @click="setFont(1)"
        >
          <i class="bi bi-plus" aria-hidden="true"></i>
        </button>
      </div>
      <button type="button" class="btn btn-sm btn-primary" @click="showForm()">
        <i class="bi bi-plus-lg me-1" aria-hidden="true"></i>{{ t('terminal.new_tab') }}
      </button>
    </div>

    <div class="row g-3">
      <div class="col-lg-9">
        <div class="card">
          <EmptyState
            v-if="tabs.length === 0"
            icon="bi-terminal"
            :title="t('terminal.no_tabs')"
            :text="t('terminal.no_tabs_hint')"
          >
            <button type="button" class="btn btn-primary btn-sm" @click="showForm()">
              {{ t('terminal.new_tab') }}
            </button>
          </EmptyState>
          <template v-else>
            <div class="card-header pb-0">
              <ul class="nav nav-tabs card-header-tabs" role="tablist">
                <li v-for="tab in tabs" :key="tab.id" class="nav-item" role="presentation">
                  <div
                    class="nav-link d-flex align-items-center gap-2 py-1"
                    :class="{ active: tab.id === activeId }"
                  >
                    <button
                      type="button"
                      class="btn btn-link btn-sm p-0 text-reset text-decoration-none ltr-island"
                      role="tab"
                      :aria-selected="tab.id === activeId"
                      @click="activeId = tab.id"
                    >
                      {{ tab.title }}
                    </button>
                    <span class="badge rounded-pill" :class="BADGE[tab.status]">&nbsp;</span>
                    <button
                      type="button"
                      class="btn-close btn-close-sm"
                      style="font-size: 0.6rem"
                      :aria-label="t('terminal.close_tab')"
                      @click="closeTab(tab.id)"
                    ></button>
                  </div>
                </li>
              </ul>
            </div>
            <div
              v-if="activeTab && activeTab.status !== 'open'"
              class="d-flex align-items-center gap-2 px-3 py-2 border-bottom small"
            >
              <span class="badge" :class="BADGE[activeTab.status]">
                {{ t(`terminal.status.${activeTab.status}`, { code: activeTab.detail.code ?? 0 }) }}
              </span>
              <span class="flex-grow-1">{{ statusText(activeTab) }}</span>
              <button
                v-if="activeTab.status !== 'connecting'"
                type="button"
                class="btn btn-sm btn-outline-primary"
                @click="reconnect(activeTab)"
              >
                {{ t('terminal.reconnect') }}
              </button>
            </div>
            <div class="ed-terminal-area">
              <div v-for="tab in tabs" v-show="tab.id === activeId" :key="tab.id" class="h-100">
                <TerminalView
                  :ref="(view) => setView(tab.id, view)"
                  :session-id="tab.id"
                  :target="tab.target"
                  :font-size="fontSize"
                  :active="tab.id === activeId"
                  @status="(status, detail) => onStatus(tab, status, detail)"
                />
              </div>
            </div>
            <div class="card-footer small text-body-secondary">{{ t('terminal.copy_hint') }}</div>
          </template>
        </div>
      </div>

      <div class="col-lg-3">
        <div class="card h-100">
          <div class="card-header d-flex align-items-center">
            <span class="fw-semibold flex-grow-1">{{ t('terminal.snippets') }}</span>
            <RouterLink to="/terminal/snippets" class="small">{{
              t('terminal.manage')
            }}</RouterLink>
          </div>
          <div class="card-body p-2">
            <p class="small text-body-secondary mb-2">{{ t('terminal.snippets_hint') }}</p>
            <input
              v-model="snippetQuery"
              type="search"
              class="form-control form-control-sm mb-2"
              :placeholder="t('terminal.search')"
              :aria-label="t('terminal.search')"
            />
            <p v-if="filteredSnippets.length === 0" class="small text-body-secondary mb-0">
              {{ t('terminal.no_snippets') }}
            </p>
            <ul v-else class="list-group list-group-flush ed-snippet-list">
              <li
                v-for="snippet in filteredSnippets"
                :key="snippet.id"
                class="list-group-item px-1"
              >
                <div class="d-flex align-items-center gap-1">
                  <span
                    class="small fw-semibold flex-grow-1 text-truncate"
                    :title="snippet.command"
                  >
                    {{ snippet.name }}
                  </span>
                  <button
                    type="button"
                    class="btn btn-sm btn-link p-0"
                    :disabled="!activeTab || activeTab.status !== 'open'"
                    @click="sendSnippet(snippet, false)"
                  >
                    {{ t('terminal.insert') }}
                  </button>
                  <button
                    type="button"
                    class="btn btn-sm btn-link p-0"
                    :disabled="!activeTab || activeTab.status !== 'open'"
                    @click="sendSnippet(snippet, true)"
                  >
                    {{ t('terminal.run') }}
                  </button>
                </div>
                <code class="d-block small text-truncate" dir="ltr">{{ snippet.command }}</code>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <EdModal v-model="formOpen" :title="t('terminal.new_tab')">
      <form id="terminal-new-tab" @submit.prevent="openTab">
        <div class="mb-3">
          <span class="form-label d-block">{{ t('terminal.mode') }}</span>
          <div class="btn-group btn-group-sm" role="group">
            <input
              id="term-mode-host"
              v-model="form.mode"
              class="btn-check"
              type="radio"
              value="host"
            />
            <label class="btn btn-outline-primary" for="term-mode-host">
              {{ t('terminal.host_shell') }}
            </label>
            <input
              id="term-mode-container"
              v-model="form.mode"
              class="btn-check"
              type="radio"
              value="container"
            />
            <label class="btn btn-outline-primary" for="term-mode-container">
              {{ t('terminal.container_shell') }}
            </label>
          </div>
        </div>
        <div v-if="form.mode === 'host'" class="mb-3">
          <label class="form-label" for="term-user">{{ t('terminal.user') }}</label>
          <input
            id="term-user"
            v-model.trim="form.user"
            class="form-control ltr-island"
            :class="{ 'is-invalid': !formValid }"
            autocomplete="off"
            spellcheck="false"
          />
          <div class="form-text">{{ t('terminal.user_hint') }}</div>
        </div>
        <div v-else class="mb-3">
          <label class="form-label" for="term-container">{{ t('terminal.container') }}</label>
          <input
            id="term-container"
            v-model.trim="form.container"
            class="form-control ltr-island"
            :class="{ 'is-invalid': form.container !== '' && !formValid }"
            autocomplete="off"
            spellcheck="false"
          />
          <div class="form-text">{{ t('terminal.container_hint') }}</div>
        </div>
        <div v-if="form.mode === 'container' || form.user === 'root'" class="mb-1">
          <label class="form-label" for="term-shell">{{ t('terminal.shell') }}</label>
          <select id="term-shell" v-model="form.shell_path" class="form-select ltr-island">
            <option v-for="shell in SHELLS" :key="shell" :value="shell">{{ shell }}</option>
          </select>
        </div>
      </form>
      <template #footer>
        <button type="button" class="btn btn-secondary" @click="formOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button
          type="submit"
          form="terminal-new-tab"
          class="btn btn-primary"
          :disabled="!formValid"
        >
          {{ t('terminal.open') }}
        </button>
      </template>
    </EdModal>
  </div>
</template>

<style scoped>
.ed-terminal-area {
  block-size: calc(100vh - 17rem);
  min-block-size: 22rem;
}

.ed-snippet-list {
  max-block-size: calc(100vh - 20rem);
  overflow-y: auto;
}
</style>
