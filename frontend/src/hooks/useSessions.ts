import { useState, useEffect } from 'react'
import { listSessions, deleteSession, type Session } from '@/api/sessions'

export function useSessions() {
  const [data, setData] = useState<Session[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = () => {
    setLoading(true)
    listSessions()
      .then((d: Session[]) => { setData(d); setError(null) })
      .catch((e: Error) => { setError(e?.message || '加载失败') })
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetch() }, [])

  const remove = async (id: string) => {
    await deleteSession(id)
    fetch()
  }

  return { data, loading, error, refetch: fetch, remove }
}
