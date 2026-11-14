<script setup lang="ts">
/** Files → File manager (§9.9). */
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { filesApi, type FileEntry } from '@/api/client'
import { ApiError } from '@/api/http'
import EdModal from '@/components/ui/EdModal.vue'
import { useApiError } from '@/composables/useApiError'
import { useConfirm } from '@/composables/useConfirm'
import { useToast } from '@/composables/useToast'
import EditorModal from '@/modules/files/components/EditorModal.vue'
import { createUploadItem, runUpload, type UploadItem } from '@/modules/files/upload'
import { useAuthStore } from '@/stores/auth'
import { useTasksStore } from '@/stores/tasks'
import { formatBytes, formatDateTime } from '@/utils/format'

const QUICK = [
  '/opt/easydeploy/www',
  '/opt/easydeploy/apps',
  '/opt/easydeploy/projects',
  '/etc/nginx',
  '/var/log',
  '/root',
  '/',
]
const ARCHIVES = /\.(zip|tar|tar\.gz|tgz|tar\.xz|txz|tar\.zst|tzst|tar\.bz2)$/i

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const apiError = useApiError()
const confirm = useConfirm()
const auth = useAuthStore()
const tasks = useTasksStore()

const path = computed(() =>
  typeof route.query.path === 'string' ? route.query.path : '/opt/easydeploy/www',
)
const entries = ref<FileEntry[]>([])
const selected = reactive(new Set<string>())
const clipboard = ref<{ mode: 'copy' | 'move'; paths: string[] } | null>(null)
const showHidden = ref(false)
const loading = ref(false)
const pathInput = ref('')
const editing = ref<string | null>(null)
const uploads = ref<UploadItem[]>([])
const dragging = ref(false)
const prompt = reactive({
  open: false,
  title: '',
  value: '',
  action: '' as 'mkdir' | 'file' | 'rename' | 'chmod',
  target: '',
  recursive: false,
})

const crumbs = computed(() => {
  const parts = path.value.split('/').filter(Boolean)
  return [
    { name: '/', path: '/' },
    ...parts.map((p, i) => ({ name: p, path: '/' + parts.slice(0, i + 1).join('/') })),
  ]
})
const join = (name: string) => (path.value === '/' ? `/${name}` : `${path.value}/${name}`)
const icon = (e: FileEntry) =>
  e.kind === 'dir'
    ? 'bi-folder-fill text-warning'
    : e.kind === 'symlink'
      ? 'bi-link-45deg'
      : ARCHIVES.test(e.name)
        ? 'bi-file-zip'
        : 'bi-file-earmark'

async function load(): Promise<void> {
  loading.value = true
  selected.clear()
  pathInput.value = path.value
  try {
    entries.value = (await filesApi.list(path.value, showHidden.value)).entries
  } catch (error) {
    toast.error(apiError.message(error))
    entries.value = []
  } finally {
    loading.value = false
  }
}

function go(target: string): void {
  void router.push({ query: { path: target || '/' } })
}

/** Run an action; if the agent says the path is protected, ask for a typed confirmation and retry. */
async function guarded(
  action: (confirmProtected: boolean) => Promise<unknown>,
  target: string,
): Promise<boolean> {
  try {
    await action(false)
    return true
  } catch (error) {
    if (error instanceof ApiError && error.code === 'fs.protected') {
      const ok = await confirm({
        title: t('files.protected_title'),
        message: t('files.protected_text'),
        danger: true,
        typeToConfirm: target,
      })
      if (ok) {
        try {
          await action(true)
          return true
        } catch (err) {
          toast.error(apiError.message(err))
        }
      }
      return false
    }
    toast.error(apiError.message(error))
    return false
  }
}

function open(e: FileEntry): void {
  if (e.kind === 'dir') go(e.path)
  else if (ARCHIVES.test(e.name)) void extract(e)
  else editing.value = e.path
}

function ask(action: typeof prompt.action, title: string, value = '', target = ''): void {
  Object.assign(prompt, { open: true, title, value, action, target, recursive: false })
}

async function submitPrompt(): Promise<void> {
  prompt.open = false
  const value = prompt.value.trim()
  if (!value) return
  let ok = false
  if (prompt.action === 'mkdir') ok = await guarded(() => filesApi.mkdir(join(value)), join(value))
  if (prompt.action === 'file')
    ok = await guarded(
      () => filesApi.write({ path: join(value), content: '', create_only: true }),
      join(value),
    )
  if (prompt.action === 'rename')
    ok = await guarded(
      (c) =>
        filesApi.move({
          sources: [prompt.target],
          destination: join(value),
          rename: true,
          confirm_protected: c,
        }),
      prompt.target,
    )
  if (prompt.action === 'chmod') {
    const paths = prompt.target ? [prompt.target] : [...selected]
    ok = await guarded(
      (c) =>
        filesApi.chmod({ paths, mode: value, recursive: prompt.recursive, confirm_protected: c }),
      paths[0] ?? '',
    )
  }
  if (ok) await load()
}

async function remove(paths: string[]): Promise<void> {
  if (!paths.length) return
  const yes = await confirm({
    title: t('files.delete'),
    message: t('files.delete_confirm', { n: paths.length }),
    danger: true,
    confirmLabel: t('files.delete'),
  })
  if (
    yes &&
    (await guarded((c) => filesApi.remove({ paths, confirm_protected: c }), paths[0] ?? ''))
  ) {
    toast.success(t('files.moved_to_recycle'))
    await load()
  }
}

async function paste(): Promise<void> {
  if (!clipboard.value) return
  const { mode, paths } = clipboard.value
  if (mode === 'move') {
    if (
      await guarded(
        (c) => filesApi.move({ sources: paths, destination: path.value, confirm_protected: c }),
        paths[0] ?? '',
      )
    ) {
      clipboard.value = null
      await load()
    }
  } else {
    const { task_id } = await filesApi.task('copy', { sources: paths, destination: path.value })
    await tasks.track(task_id)
  }
}

async function startTask(action: string, body: Record<string, unknown>): Promise<void> {
  try {
    const { task_id } = await filesApi.task(action, body)
    await tasks.track(task_id)
  } catch (error) {
    toast.error(apiError.message(error))
  }
}

const extract = (e: FileEntry) =>
  startTask('extract', { archive: e.path, destination: join(e.name.replace(ARCHIVES, '')) })
const compress = () =>
  startTask('compress', {
    paths: [...selected],
    destination: join(`archive-${Date.now()}.zip`),
    format: 'zip',
  })
const download = (e: FileEntry) =>
  window.open(`/api/v1/files/download?path=${encodeURIComponent(e.path)}`, '_blank')

function addFiles(files: FileList | File[] | null): void {
  for (const file of Array.from(files ?? [])) {
    const item = createUploadItem(file, path.value)
    uploads.value.push(item)
    void runUpload(item).then(() => {
      if (item.state === 'done') void load()
    })
  }
}

function onDrop(event: DragEvent): void {
  dragging.value = false
  addFiles(event.dataTransfer?.files ?? null)
}

watch([path, showHidden], load, { immediate: true })
</script>

<template>
  <div
    @dragover.prevent="dragging = true"
    @dragleave.self="dragging = false"
    @drop.prevent="onDrop"
  >
    <h1 class="h4 mb-3">{{ t('nav.files.manager') }}</h1>
    <div class="card">
      <div class="card-body border-bottom d-flex flex-wrap gap-2 align-items-center">
        <nav class="flex-grow-1 ltr-island" :aria-label="t('files.location')">
          <ol class="breadcrumb mb-0">
            <li v-for="c in crumbs" :key="c.path" class="breadcrumb-item">
              <a href="#" @click.prevent="go(c.path)">{{ c.name }}</a>
            </li>
          </ol>
        </nav>
        <form class="d-flex gap-1" @submit.prevent="go(pathInput)">
          <input
            v-model="pathInput"
            class="form-control form-control-sm ltr-island"
            style="width: 16rem"
            :aria-label="t('files.location')"
          />
          <select
            class="form-select form-select-sm w-auto"
            :aria-label="t('files.quick')"
            @change="go(($event.target as HTMLSelectElement).value)"
          >
            <option value="">{{ t('files.quick') }}</option>
            <option v-for="q in QUICK" :key="q" :value="q">{{ q }}</option>
          </select>
        </form>
      </div>
      <div class="card-body border-bottom d-flex flex-wrap gap-1">
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary"
          @click="go(path.split('/').slice(0, -1).join('/') || '/')"
        >
          <i class="bi bi-arrow-up" aria-hidden="true"></i> {{ t('files.up') }}
        </button>
        <button type="button" class="btn btn-sm btn-outline-secondary" @click="load">
          {{ t('common.refresh') }}
        </button>
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary"
          @click="ask('mkdir', t('files.new_folder'))"
        >
          {{ t('files.new_folder') }}
        </button>
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary"
          @click="ask('file', t('files.new_file'))"
        >
          {{ t('files.new_file') }}
        </button>
        <label class="btn btn-sm btn-primary mb-0">
          <i class="bi bi-upload" aria-hidden="true"></i> {{ t('files.upload') }}
          <input
            type="file"
            multiple
            hidden
            @change="addFiles(($event.target as HTMLInputElement).files)"
          />
        </label>
        <button v-if="clipboard" type="button" class="btn btn-sm btn-success" @click="paste">
          {{ t('files.paste', { n: clipboard.paths.length }) }}
        </button>
        <template v-if="selected.size">
          <span class="vr mx-1"></span>
          <button
            type="button"
            class="btn btn-sm btn-outline-secondary"
            @click="clipboard = { mode: 'copy', paths: [...selected] }"
          >
            {{ t('files.copy') }}
          </button>
          <button
            type="button"
            class="btn btn-sm btn-outline-secondary"
            @click="clipboard = { mode: 'move', paths: [...selected] }"
          >
            {{ t('files.cut') }}
          </button>
          <button type="button" class="btn btn-sm btn-outline-secondary" @click="compress">
            {{ t('files.compress') }}
          </button>
          <button
            type="button"
            class="btn btn-sm btn-outline-secondary"
            @click="ask('chmod', t('files.permissions'), '0644')"
          >
            {{ t('files.permissions') }}
          </button>
          <button
            type="button"
            class="btn btn-sm btn-outline-danger"
            @click="remove([...selected])"
          >
            {{ t('files.delete') }}
          </button>
        </template>
        <div class="form-check form-switch ms-auto">
          <input id="fm-hidden" v-model="showHidden" class="form-check-input" type="checkbox" />
          <label class="form-check-label small" for="fm-hidden">{{ t('files.hidden') }}</label>
        </div>
      </div>
      <div v-if="dragging" class="alert alert-info m-2 text-center">{{ t('files.drop_here') }}</div>
      <div
        v-for="u in uploads.filter((x) => x.state !== 'done')"
        :key="u.key"
        class="px-3 py-2 border-bottom small d-flex align-items-center gap-2"
      >
        <span class="text-truncate ltr-island" style="max-width: 20rem">{{ u.file.name }}</span>
        <div class="progress flex-grow-1" style="height: 0.4rem">
          <div class="progress-bar" :style="{ width: `${u.progress}%` }"></div>
        </div>
        <span>{{ u.progress }}%</span>
        <button
          v-if="u.state === 'uploading'"
          type="button"
          class="btn btn-sm btn-link"
          @click="u.state = 'paused'"
        >
          {{ t('files.pause') }}
        </button>
        <button v-else type="button" class="btn btn-sm btn-link" @click="runUpload(u).then(load)">
          {{ t('files.resume') }}
        </button>
        <span v-if="u.error" class="text-danger">{{ u.error }}</span>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-hover align-middle mb-0">
          <thead>
            <tr>
              <th style="width: 2rem"></th>
              <th>{{ t('files.name') }}</th>
              <th class="text-end">{{ t('files.size') }}</th>
              <th class="d-none d-md-table-cell">{{ t('files.mode') }}</th>
              <th class="d-none d-md-table-cell">{{ t('files.owner') }}</th>
              <th class="d-none d-lg-table-cell">{{ t('files.modified') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in entries" :key="e.path">
              <td>
                <input
                  class="form-check-input"
                  type="checkbox"
                  :checked="selected.has(e.path)"
                  :aria-label="e.name"
                  @change="selected.has(e.path) ? selected.delete(e.path) : selected.add(e.path)"
                />
              </td>
              <td class="ltr-island">
                <a href="#" class="text-body" @click.prevent="open(e)"
                  ><i class="bi me-1" :class="icon(e)" aria-hidden="true"></i>{{ e.name }}</a
                >
                <small v-if="e.link_target" class="text-body-secondary">
                  → {{ e.link_target }}</small
                >
                <i
                  v-if="e.protected"
                  class="bi bi-shield-lock text-body-secondary ms-1"
                  :title="t('files.protected_title')"
                ></i>
              </td>
              <td class="text-end small">{{ e.kind === 'dir' ? '' : formatBytes(e.size, t) }}</td>
              <td class="d-none d-md-table-cell">
                <code>{{ e.mode }}</code>
              </td>
              <td class="d-none d-md-table-cell small ltr-island">{{ e.owner }}:{{ e.group }}</td>
              <td class="d-none d-lg-table-cell small">
                {{
                  formatDateTime(
                    new Date(e.mtime * 1000).toISOString(),
                    auth.user?.calendar ?? 'gregorian',
                  )
                }}
              </td>
              <td class="text-end text-nowrap">
                <button
                  v-if="e.kind === 'file'"
                  type="button"
                  class="btn btn-sm btn-link px-1"
                  @click="download(e)"
                >
                  {{ t('files.download') }}
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-link px-1"
                  @click="ask('rename', t('files.rename'), e.name, e.path)"
                >
                  {{ t('files.rename') }}
                </button>
                <button
                  v-if="e.kind === 'dir'"
                  type="button"
                  class="btn btn-sm btn-link px-1"
                  @click="startTask('du', { path: e.path })"
                >
                  {{ t('files.size') }}
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-link px-1 text-danger"
                  @click="remove([e.path])"
                >
                  {{ t('files.delete') }}
                </button>
              </td>
            </tr>
            <tr v-if="!loading && entries.length === 0">
              <td colspan="7" class="text-center text-body-secondary py-4">
                {{ t('common.empty') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <EdModal v-model="prompt.open" :title="prompt.title" size="sm">
      <form id="fm-prompt" @submit.prevent="submitPrompt">
        <input
          v-model="prompt.value"
          class="form-control ltr-island"
          autofocus
          :aria-label="prompt.title"
        />
        <div v-if="prompt.action === 'chmod'" class="form-check mt-2">
          <input id="fm-rec" v-model="prompt.recursive" class="form-check-input" type="checkbox" />
          <label class="form-check-label" for="fm-rec">{{ t('files.recursive') }}</label>
        </div>
      </form>
      <template #footer>
        <button type="submit" form="fm-prompt" class="btn btn-primary">
          {{ t('common.confirm') }}
        </button>
      </template>
    </EdModal>
    <EditorModal :path="editing" @close="editing = null" @saved="load" />
  </div>
</template>
