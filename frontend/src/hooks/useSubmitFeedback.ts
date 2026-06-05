import { useState } from 'react'
import { submitFeedback } from '@/api/feedbacks'

export function useSubmitFeedback() {
  const [submitted, setSubmitted] = useState<Record<string, boolean>>({})

  const submit = async (traceId: string, rating: number, feedbackType: string, comment?: string) => {
    await submitFeedback({ trace_id: traceId, rating, feedback_type: feedbackType, comment })
    setSubmitted(s => ({ ...s, [traceId]: true }))
  }

  return { submitted, submit }
}
