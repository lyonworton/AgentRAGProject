import { request } from './client'

export interface Session {
  id: string
  user_id: string
  collection_id: string | null
  title: string | null
  message_count: number
  is_active: boolean
  last_activity_at: string | null
}

export interface Message {
  id: string
  session_id: string
  role: string
  content: string
  trace_id: string | null
  citations: any | null
  token_count: number | null
  created_at: string | null
}

export function createSession(colId?: string, title?: string): Promise<Session> {
  return request<Session>('/sessions', {
    method: 'POST',
    body: JSON.stringify({ collection_id: colId, title }),
  })
}

export function listSessions(): Promise<Session[]> {
  return request<Session[]>('/sessions')
}

export function getSession(id: string): Promise<Session> {
  return request<Session>(`/sessions/${id}`)
}

export function deleteSession(id: string): Promise<void> {
  return request<void>(`/sessions/${id}`, { method: 'DELETE' })
}

export function getSessionHistory(id: string): Promise<{ messages: Message[] }> {
  return request<{ messages: Message[] }>(`/sessions/${id}/history`)
}
