<script setup lang="ts">
/** Monaco editor (loaded lazily, LTR island) bound with v-model. */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{ modelValue: string; filename?: string; dark?: boolean }>(),
  {
    filename: '',
    dark: false,
  },
)
const emit = defineEmits<{ 'update:modelValue': [value: string]; save: [] }>()

const el = ref<HTMLDivElement | null>(null)
type Monaco = typeof import('monaco-editor')
let monaco: Monaco | null = null
let editor: import('monaco-editor').editor.IStandaloneCodeEditor | null = null

const LANGUAGES: Record<string, string> = {
  js: 'javascript',
  mjs: 'javascript',
  ts: 'typescript',
  json: 'json',
  py: 'python',
  php: 'php',
  sh: 'shell',
  bash: 'shell',
  yml: 'yaml',
  yaml: 'yaml',
  md: 'markdown',
  html: 'html',
  htm: 'html',
  css: 'css',
  scss: 'scss',
  sql: 'sql',
  xml: 'xml',
  ini: 'ini',
  conf: 'ini',
  go: 'go',
  java: 'java',
  rs: 'rust',
  rb: 'ruby',
  dockerfile: 'dockerfile',
  env: 'ini',
  vue: 'html',
  toml: 'ini',
}

function languageFor(name: string): string {
  const lower = name.toLowerCase()
  if (lower === 'dockerfile') return 'dockerfile'
  return LANGUAGES[lower.split('.').pop() ?? ''] ?? 'plaintext'
}

onMounted(async () => {
  const [loaded, { default: EditorWorker }] = await Promise.all([
    import('monaco-editor'),
    import('monaco-editor/esm/vs/editor/editor.worker?worker'),
  ])
  monaco = loaded
  ;(self as unknown as { MonacoEnvironment: unknown }).MonacoEnvironment = {
    getWorker: () => new EditorWorker(),
  }
  if (!el.value) return
  editor = monaco.editor.create(el.value, {
    value: props.modelValue,
    language: languageFor(props.filename),
    theme: props.dark ? 'vs-dark' : 'vs',
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 13,
    scrollBeyondLastLine: false,
  })
  editor.onDidChangeModelContent(() => emit('update:modelValue', editor?.getValue() ?? ''))
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => emit('save'))
})

watch(
  () => props.modelValue,
  (value) => {
    if (editor && value !== editor.getValue()) editor.setValue(value)
  },
)

onBeforeUnmount(() => {
  editor?.getModel()?.dispose()
  editor?.dispose()
})
</script>

<template>
  <div ref="el" dir="ltr" class="border rounded" style="height: 65vh"></div>
</template>
