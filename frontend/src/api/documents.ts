import { request } from './client'

export interface Document {
  id: string
  title: string
  source_type: string
  mime_type: string | null
  file_size: number | null
  status: string
  chunk_count: number
  ingested_at: string | null
}

export function listDocuments(colId: string): Promise<Document[]> {
  return request<Document[]>(`/collections/${colId}/documents`)
}

export function deleteDocument(colId: string, docId: string): Promise<void> {
  return request<void>(`/collections/${colId}/documents/${docId}`, { method: 'DELETE' })
}
