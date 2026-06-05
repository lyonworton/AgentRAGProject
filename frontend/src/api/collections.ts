import { request } from './client'

export interface Collection {
  id: string
  name: string
  description: string | null
  config: Record<string, any> | null
  doc_count: number
  chunk_count: number
  status: string
}

export function listCollections(): Promise<Collection[]> {
  return request<Collection[]>('/collections')
}

export function getCollection(id: string): Promise<Collection> {
  return request<Collection>(`/collections/${id}`)
}

export function createCollection(name: string, description?: string): Promise<Collection> {
  return request<Collection>('/collections', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  })
}

export function deleteCollection(id: string): Promise<void> {
  return request<void>(`/collections/${id}`, { method: 'DELETE' })
}
