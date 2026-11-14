/** Light / dark / system theme through Bootstrap color modes (`data-bs-theme` on <html>). */
import { ref } from 'vue'

export type ThemeChoice = 'light' | 'dark' | 'system'
const STORAGE_KEY = 'ed.theme'

const choice = ref<ThemeChoice>(readStored())
let media: MediaQueryList | null = null

function readStored(): ThemeChoice {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    if (value === 'light' || value === 'dark' || value === 'system') return value
  } catch {
    // storage unavailable
  }
  return 'system'
}

export function resolveTheme(value: ThemeChoice, prefersDark: boolean): 'light' | 'dark' {
  if (value === 'system') return prefersDark ? 'dark' : 'light'
  return value
}

function apply(): void {
  const prefersDark = media?.matches ?? false
  document.documentElement.setAttribute('data-bs-theme', resolveTheme(choice.value, prefersDark))
}

export function initTheme(): void {
  if (typeof window.matchMedia === 'function') {
    media = window.matchMedia('(prefers-color-scheme: dark)')
    media.addEventListener('change', apply)
  }
  apply()
}

export function useTheme() {
  function setTheme(value: ThemeChoice): void {
    choice.value = value
    try {
      localStorage.setItem(STORAGE_KEY, value)
    } catch {
      // storage unavailable
    }
    apply()
  }
  return { theme: choice, setTheme }
}
