/** App-wide toast notifications rendered by `EdToastHost` (Bootstrap toasts). */
import { reactive } from 'vue'

export type ToastVariant = 'success' | 'danger' | 'warning' | 'info'

export interface ToastMessage {
  id: number
  text: string
  variant: ToastVariant
  detail?: string
}

let nextId = 1
export const toasts = reactive<ToastMessage[]>([])

export function dismissToast(id: number): void {
  const index = toasts.findIndex((t) => t.id === id)
  if (index >= 0) toasts.splice(index, 1)
}

export function useToast() {
  function push(variant: ToastVariant, text: string, detail?: string): void {
    toasts.push({ id: nextId++, text, variant, detail })
  }
  return {
    success: (text: string) => push('success', text),
    error: (text: string, detail?: string) => push('danger', text, detail),
    warning: (text: string) => push('warning', text),
    info: (text: string) => push('info', text),
  }
}
