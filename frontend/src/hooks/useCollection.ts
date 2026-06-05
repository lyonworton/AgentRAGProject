import { useState, useEffect } from 'react'
import { getCollection, type Collection } from '@/api/collections'

export function useCollection(id: string | undefined) {
  const [data, setData] = useState<Collection | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    getCollection(id)
      .then(d => { setData(d); setError(null) })
      .catch(e => { setData(null); setError(e?.message || '加载失败') })
      .finally(() => setLoading(false))
  }, [id])

  return { data, loading, error }
}
