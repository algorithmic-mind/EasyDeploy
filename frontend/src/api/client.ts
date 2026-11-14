/**
 * Typed API endpoints. Types come from `schema.d.ts`, generated from the backend OpenAPI schema
 * (`npm run gen:api`); CI fails when the committed schema is stale.
 */
import type { components } from './schema'
import { http, type Query } from './http'

type S = components['schemas']

export type User = S['User']
export type Me = S['Me']
export type LoginResult = S['LoginResult']
export type TotpSetup = S['TotpSetup']
export type RecoveryCodes = S['RecoveryCodes']
export type Task = S['Task']
export type TaskStatus = S['TaskStatusEnum']
export type PaginatedTasks = S['PaginatedTaskList']
export type PanelInfo = S['PanelInfo']
export type SystemInfo = S['SystemInfo']
export type ApiKey = S['ApiKey']
export type ApiKeyCreated = S['ApiKeyCreated']
export type HistoryPoint = S['HistoryPoint']

const V1 = '/api/v1'

export const authApi = {
  csrf: () => http.get<void>(`${V1}/auth/csrf`),
  login: (body: S['LoginRequest']) => http.post<LoginResult>(`${V1}/auth/login`, body),
  secondFactor: (body: S['SecondFactorRequest']) =>
    http.post<LoginResult>(`${V1}/auth/login/2fa`, body),
  logout: () => http.post<void>(`${V1}/auth/logout`),
  me: () => http.get<Me>(`${V1}/auth/me`),
  updateMe: (body: S['PatchedUserRequest']) => http.patch<Me>(`${V1}/auth/me`, body),
  sudo: (body: S['SudoRequest']) => http.post<S['SudoResult']>(`${V1}/auth/sudo`, body),
  changePassword: (body: S['PasswordChangeRequest']) =>
    http.post<void>(`${V1}/auth/password`, body),
  totpSetup: () => http.post<TotpSetup>(`${V1}/auth/2fa/setup`),
  totpEnable: (body: S['TotpCodeRequest']) =>
    http.post<RecoveryCodes>(`${V1}/auth/2fa/enable`, body),
  totpDisable: () => http.post<void>(`${V1}/auth/2fa/disable`),
  recoveryCodes: () => http.post<RecoveryCodes>(`${V1}/auth/2fa/recovery-codes`),
}

export const panelApi = {
  info: () => http.get<PanelInfo>(`${V1}/panel/info`),
}

export const dashboardApi = {
  systemInfo: () => http.get<SystemInfo>(`${V1}/dashboard/system-info`),
}

export const monitoringApi = {
  history: (range: string) => http.get<S['MetricsHistory']>(`${V1}/monitoring/history`, { range }),
}

export const tasksApi = {
  list: (query?: Query) => http.get<PaginatedTasks>(`${V1}/tasks`, query),
  get: (id: string) => http.get<Task>(`${V1}/tasks/${id}`),
  log: (id: string) => http.get<S['TaskLog']>(`${V1}/tasks/${id}/log`),
  cancel: (id: string) => http.post<Task>(`${V1}/tasks/${id}/cancel`),
  diagnostics: () => http.post<S['TaskAccepted']>(`${V1}/tasks/diagnostics`),
}
