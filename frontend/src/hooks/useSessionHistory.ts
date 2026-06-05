import { useState, useEffect } from 'react'
import { getSessionHistory, type Message } from '@/api/sessions'

export function useSessionHistory(sessionId: string | undefined) {
  const [data, setData] = useState<Message[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) { setData(null); return }
    setLoading(true)
    getSessionHistory(sessionId)
      .then((d: { messages: Message[] }) => { setData(d.messages); setError(null) })
      .catch((e: Error) => { setError(e?.message || '加载失败') })
      .finally(() => setLoading(false))
  }, [sessionId])

  return { data, loading, error }
}
