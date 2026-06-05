import { request } from './client'

export function submitFeedback(data: {
  trace_id: string
  rating?: number
  feedback_type?: string
  comment?: string
}): Promise<any> {
  return request('/feedback', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
