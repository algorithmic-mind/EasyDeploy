/**
 * Resumable chunked upload (§9.9): create an upload, ask which chunks the server already has,
 * send the rest with a SHA-256 per chunk, then complete. `pause()` stops after the current chunk;
 * `start()` again resumes where the server left off.
 */
import { reactive } from 'vue'

import { readCookie } from '@/api/http'
import { filesApi } from '@/api/client'

export type UploadState = 'queued' | 'uploading' | 'paused' | 'done' | 'error'

export interface UploadItem {
  key: string
  file: File
  directory: string
  progress: number
  state: UploadState
  error: string
  uploadId: string | null
}

const isPaused = (item: UploadItem) => item.state === 'paused'

async function sha256(data: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', data)
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('')
}

async function putChunk(uploadId: string, index: number, blob: Blob): Promise<void> {
  const buffer = await blob.arrayBuffer()
  const response = await fetch(`/api/v1/files/uploads/${uploadId}/chunks/${index}`, {
    method: 'PUT',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/octet-stream',
      'X-Chunk-SHA256': await sha256(buffer),
      'X-CSRFToken': readCookie('ed_csrftoken') ?? '',
    },
    body: buffer,
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { message?: string }
    } | null
    throw new Error(body?.error?.message ?? `HTTP ${response.status}`)
  }
}

export function createUploadItem(file: File, directory: string): UploadItem {
  return reactive({
    key: `${directory}/${file.name}/${file.size}/${file.lastModified}`,
    file,
    directory,
    progress: 0,
    state: 'queued' as UploadState,
    error: '',
    uploadId: null,
  })
}

export async function runUpload(item: UploadItem, overwrite = false): Promise<void> {
  item.state = 'uploading'
  item.error = ''
  try {
    if (!item.uploadId) {
      const created = await filesApi.createUpload({
        directory: item.directory,
        filename: item.file.name,
        size: item.file.size,
        overwrite,
      })
      item.uploadId = created.id
    }
    const status = await filesApi.uploadStatus(item.uploadId)
    const have = new Set(status.received)
    for (let index = 0; index < status.total_chunks; index++) {
      if (isPaused(item)) return
      if (!have.has(index)) {
        const start = index * status.chunk_size
        await putChunk(item.uploadId, index, item.file.slice(start, start + status.chunk_size))
        have.add(index)
      }
      item.progress = Math.round((have.size / status.total_chunks) * 100)
    }
    await filesApi.completeUpload(item.uploadId)
    item.state = 'done'
    item.progress = 100
  } catch (error) {
    item.state = 'error'
    item.error = error instanceof Error ? error.message : String(error)
  }
}
