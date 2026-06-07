import { useState, useEffect, useCallback } from 'react'
import { listCollections, type Collection } from '@/api/collections'

interface State {
  data: Collection[] | null
  loading: boolean
  error: string | null
}

export function useCollections() {
  const [state, setState] = useState<State>({ data: null, loading: true, error: null })

  const fetch = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: null }))
    try {
      const data = await listCollections()
      setState({ data, loading: false, error: null })
    } catch (e: any) {
      setState({ data: null, loading: false, error: e?.message || 'Load failed' })
    }
  }, [])

  useEffect(() => { fetch() }, [fetch])

  return { ...state, refetch: fetch }
}
