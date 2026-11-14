/** Promise-based confirmation dialog rendered once by `ConfirmDialog` (§10.6). */
import { ref } from 'vue'

export interface ConfirmOptions {
  title: string
  message: string
  confirmLabel?: string
  danger?: boolean
  /** Critical deletes: the user must type this text to enable the button. */
  typeToConfirm?: string
}

export const confirmRequest = ref<(ConfirmOptions & { resolve: (ok: boolean) => void }) | null>(
  null,
)

export function useConfirm() {
  return (options: ConfirmOptions): Promise<boolean> =>
    new Promise((resolve) => {
      confirmRequest.value = { ...options, resolve }
    })
}
