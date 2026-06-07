import { useState, useEffect } from 'react'
import { listIngestJobs, type IngestJob } from '@/api/ingestion'

export function useIngestionJobs(params?: { collection_id?: string; limit?: number }) {
  const [data, setData] = useState<IngestJob[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = () => {
    setLoading(true)
    listIngestJobs(params)
      .then((d: IngestJob[]) => { setData(d); setError(null) })
      .catch((e: Error) => { setData(null); setError(e?.message || 'Load failed') })
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetch() }, [params?.collection_id, params?.limit])

  return { data, loading, error, refetch: fetch }
}
