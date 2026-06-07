import { useState } from 'react'
import { useCollections } from '@/hooks/useCollections'
import { useIngestionJobs } from '@/hooks/useIngestionJobs'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorBanner } from '@/components/shared/ErrorBanner'
import { EmptyState } from '@/components/shared/EmptyState'
import { Card, CardContent } from '@/components/ui/card'

export function IngestionJobs() {
  const { data: cols } = useCollections()
  const [filterColId, setFilterColId] = useState('')
  const { data: jobs, loading, error, refetch } = useIngestionJobs(
    filterColId ? { collection_id: filterColId, limit: 50 } : { limit: 50 }
  )
  const [expanded, setExpanded] = useState<string | null>(null)

  if (loading) return <LoadingSpinner />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Ingestion Jobs</h1>
        <div className="flex items-center gap-2">
          <select className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm" value={filterColId} onChange={e => setFilterColId(e.target.value)}>
            <option value="">All Collections</option>
            {cols?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
      </div>

      {(!jobs || jobs.length === 0) ? (
        <EmptyState title="No ingestion jobs yet" />
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="p-3 font-medium">Job ID</th>
                  <th className="p-3 font-medium">Collection</th>
                  <th className="p-3 font-medium">Source</th>
                  <th className="p-3 font-medium">Progress</th>
                  <th className="p-3 font-medium">Status</th>
                  <th className="p-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(j => (
                  <>
                    <tr key={j.id} className="border-b last:border-0 hover:bg-muted/50 cursor-pointer" onClick={() => setExpanded(expanded === j.id ? null : j.id)}>
                      <td className="p-3 font-mono text-xs">{j.id.slice(0, 8)}</td>
                      <td className="p-3 font-mono text-xs">{j.collection_id.slice(0, 8)}</td>
                      <td className="p-3"><StatusBadge status={j.source_type} /></td>
                      <td className="p-3">{j.completed_docs}/{j.total_docs}</td>
                      <td className="p-3"><StatusBadge status={j.status} /></td>
                      <td className="p-3 text-xs text-muted-foreground">{j.created_at ? new Date(j.created_at).toLocaleString() : '-'}</td>
                    </tr>
                    {expanded === j.id && j.errors && j.errors.length > 0 && (
                      <tr key={`${j.id}-err`} className="bg-muted/30">
                        <td colSpan={6} className="p-3">
                          <pre className="text-xs text-destructive whitespace-pre-wrap">{JSON.stringify(j.errors, null, 2)}</pre>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}