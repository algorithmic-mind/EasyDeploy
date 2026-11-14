/**
 * Sudo mode (§9.1): run an action; if the API answers `auth.sudo_required`, ask for the password
 * in the global SudoModal, then retry once.
 */
import { ref } from 'vue'

import { ApiError } from '@/api/http'

export const sudoPrompt = ref<{ resolve: (ok: boolean) => void } | null>(null)

function askForSudo(): Promise<boolean> {
  return new Promise((resolve) => {
    sudoPrompt.value = { resolve }
  })
}

export function useSudo() {
  async function run<T>(action: () => Promise<T>): Promise<T | undefined> {
    try {
      return await action()
    } catch (error) {
      if (!(error instanceof ApiError) || error.code !== 'auth.sudo_required') throw error
      const confirmed = await askForSudo()
      if (!confirmed) return undefined
      return await action()
    }
  }
  return { run }
}
