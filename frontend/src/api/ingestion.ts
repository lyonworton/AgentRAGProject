import { request } from './client'

export interface IngestJob {
  id: string
  collection_id: string
  source_type: string
  status: string
  total_docs: number
  completed_docs: number
  failed_docs: number
  errors: string[]
  started_at: string | null
  completed_at: string | null
  created_at: string | null
}

export function listIngestJobs(params?: { collection_id?: string; limit?: number }): Promise<IngestJob[]> {
  const qs = new URLSearchParams()
  if (params?.collection_id) qs.set('collection_id', params.collection_id)
  if (params?.limit) qs.set('limit', String(params.limit))
  const q = qs.toString()
  return request<IngestJob[]>(`/ingest${q ? '?' + q : ''}`)
}

export function getIngestJob(jobId: string): Promise<IngestJob> {
  return request<IngestJob>(`/ingest/${jobId}`)
}

export function ingestLocal(colId: string, files: File[]): Promise<{ job_id: string; arq_job_id: string; file_count: number }> {
  const fd = new FormData()
  fd.append('collection_id', colId)
  files.forEach(f => fd.append('files', f))
  const token = localStorage.getItem('token')
  return fetch('/api/v1/ingest/local', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd,
  }).then(res => {
    if (!res.ok) throw new Error(`Ingest failed: ${res.status}`)
    return res.json()
  })
}

export function ingestWeb(colId: string, urls: string[]): Promise<{ job_id: string; arq_job_id: string }> {
  return request('/ingest/web', {
    method: 'POST',
    body: JSON.stringify({ collection_id: colId, urls }),
  })
}

export function ingestDatabase(
  colId: string, dbUrl: string, query: string, titleColumn: string, contentColumns: string[]
): Promise<{ job_id: string; arq_job_id: string }> {
  return request('/ingest/database', {
    method: 'POST',
    body: JSON.stringify({
      collection_id: colId, db_url: dbUrl, query,
      title_column: titleColumn, content_columns: contentColumns,
    }),
  })
}
