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
export type AuditRow = S['AuditLog']
export type LoginRow = S['LoginLog']
export type Snippet = S['Snippet']

export interface FileEntry {
  name: string
  path: string
  kind: 'file' | 'dir' | 'symlink' | 'other'
  size: number
  mode: string
  owner: string
  group: string
  mtime: number
  link_target: string | null
  protected?: boolean
}

export interface RecycleItem {
  id: string
  original_path: string
  deleted_at: number
  size: number
  kind: string
}

interface FileList {
  path: string
  entries: FileEntry[]
  truncated: boolean
  protected: boolean
}

export interface ProcessRow {
  pid: number
  ppid: number
  name: string
  username: string
  status: string
  cpu_percent: number
  memory_rss: number
  memory_percent: number
  num_threads: number
  create_time: number
  cmdline: string
}

export interface UnitRow {
  unit: string
  description: string
  load_state: string
  active_state: string
  sub_state: string
  unit_file_state: string
  protected: boolean
}

export interface JournalEntry {
  timestamp: number
  unit: string
  identifier: string
  priority: number
  message: string
  pid: number | null
}

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

export const hostApi = {
  processes: (sort: string) => http.get<S['ProcessList']>(`${V1}/host/processes`, { sort }),
  signal: (pid: number, signal: string) =>
    http.post<S['SignalResult']>(`${V1}/host/processes/${pid}/signal`, { signal }),
  services: () => http.get<S['ServiceList']>(`${V1}/host/services`),
  serviceAction: (unit: string, action: string) =>
    http.post<S['ServiceActionResult']>(`${V1}/host/services/${encodeURIComponent(unit)}/action`, {
      action,
    }),
  journal: (query: Query) => http.get<S['JournalResult']>(`${V1}/host/journal`, query),
}

type Body = Record<string, unknown>

export const filesApi = {
  list: (path: string, hidden: boolean) => http.get<FileList>(`${V1}/files/list`, { path, hidden }),
  read: (path: string) => http.get<Record<string, unknown>>(`${V1}/files/content`, { path }),
  write: (body: {
    path: string
    content: string
    expected_sha256?: string
    create_only?: boolean
  }) => http.put<Record<string, unknown>>(`${V1}/files/content`, body),
  mkdir: (path: string) => http.post<Body>(`${V1}/files/mkdir`, { path }),
  move: (body: {
    sources: string[]
    destination: string
    rename?: boolean
    overwrite?: boolean
    confirm_protected?: boolean
  }) => http.post<Body>(`${V1}/files/move`, body),
  remove: (body: { paths: string[]; confirm_protected?: boolean }) =>
    http.post<Body>(`${V1}/files/delete`, body),
  chmod: (body: {
    paths: string[]
    mode: string
    recursive?: boolean
    confirm_protected?: boolean
  }) => http.post<Body>(`${V1}/files/chmod`, body),
  recycle: () => http.get<{ items: RecycleItem[] }>(`${V1}/files/recycle`),
  restore: (ids: string[]) => http.post<Body>(`${V1}/files/recycle/restore`, { ids }),
  purge: (body: { ids?: string[]; all?: boolean }) =>
    http.post<Body>(`${V1}/files/recycle/purge`, body),
  task: (action: string, body: Body) =>
    http.post<{ task_id: string }>(`${V1}/files/tasks/${action}`, body),
  createUpload: (body: {
    directory: string
    filename: string
    size: number
    overwrite?: boolean
  }) => http.post<S['UploadStatus']>(`${V1}/files/uploads`, body),
  uploadStatus: (id: string) => http.get<S['UploadStatus']>(`${V1}/files/uploads/${id}`),
  completeUpload: (id: string) => http.post<Body>(`${V1}/files/uploads/${id}/complete`),
}

export const terminalApi = {
  check: () => http.post<S['TerminalCheck']>(`${V1}/terminal/check`),
  snippets: (query?: Query) =>
    http.get<S['PaginatedSnippetList']>(`${V1}/terminal/snippets`, { page_size: 200, ...query }),
  createSnippet: (body: S['SnippetRequest']) => http.post<Snippet>(`${V1}/terminal/snippets`, body),
  updateSnippet: (id: string, body: S['PatchedSnippetRequest']) =>
    http.patch<Snippet>(`${V1}/terminal/snippets/${id}`, body),
  deleteSnippet: (id: string) => http.delete<void>(`${V1}/terminal/snippets/${id}`),
}

export const logsApi = {
  audit: (query: Query) => http.get<S['PaginatedAuditLogList']>(`${V1}/audit/logs`, query),
  logins: (query: Query) => http.get<S['PaginatedLoginLogList']>(`${V1}/audit/login-logs`, query),
}

export const tasksApi = {
  list: (query?: Query) => http.get<PaginatedTasks>(`${V1}/tasks`, query),
  get: (id: string) => http.get<Task>(`${V1}/tasks/${id}`),
  log: (id: string) => http.get<S['TaskLog']>(`${V1}/tasks/${id}/log`),
  cancel: (id: string) => http.post<Task>(`${V1}/tasks/${id}/cancel`),
  diagnostics: () => http.post<S['TaskAccepted']>(`${V1}/tasks/diagnostics`),
}
