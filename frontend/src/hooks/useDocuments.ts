import { useState, useEffect } from 'react'
import { listDocuments, type Document } from '@/api/documents'

export function useDocuments(colId: string | undefined) {
  const [data, setData] = useState<Document[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = () => {
    if (!colId) return
    setLoading(true)
    listDocuments(colId)
      .then(d => { setData(d); setError(null) })
      .catch(e => { setData(null); setError(e?.message || 'Load failed') })
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetch() }, [colId])

  return { data, loading, error, refetch: fetch }
}
