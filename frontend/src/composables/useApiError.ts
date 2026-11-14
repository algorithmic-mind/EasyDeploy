/** Turn any thrown value into a user-facing message (server messages are already localized). */
import { useI18n } from 'vue-i18n'

import { ApiError } from '@/api/http'

export function useApiError() {
  const { t } = useI18n()

  function message(error: unknown): string {
    if (error instanceof ApiError) return error.message || t('common.error_generic')
    if (error instanceof TypeError) return t('common.error_network')
    return t('common.error_generic')
  }

  function requestId(error: unknown): string | undefined {
    return error instanceof ApiError && error.requestId
      ? t('common.request_id', { id: error.requestId })
      : undefined
  }

  return { message, requestId }
}
