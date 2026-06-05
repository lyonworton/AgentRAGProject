import { request } from './client'

export function queryRAG(query: string, collectionIds: string[], sessionId?: string): Promise<{
  answer: string; citations: any[]; agent_trace: any; uncertainty_flags: any[]; trace_id: string
}> {
  return request('/query', {
    method: 'POST',
    body: JSON.stringify({ query, collection_ids: collectionIds, session_id: sessionId }),
  })
}
