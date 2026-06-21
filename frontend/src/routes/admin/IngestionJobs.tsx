import { useState } from 'react'
import { Trash2, Square, Filter } from 'lucide-react'
import { useCollections } from '@/hooks/useCollections'
import { useIngestionJobs } from '@/hooks/useIngestionJobs'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorBanner } from '@/components/shared/ErrorBanner'
import { EmptyState } from '@/components/shared/EmptyState'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { deleteIngestJob, cancelIngestJob } from '@/api/ingestion'
import { cn } from '@/lib/utils'

export function IngestionJobs() {
  const { data: cols } = useCollections()
  const [filterColId, setFilterColId] = useState('')
  const { data: jobs, loading, error, refetch } = useIngestionJobs(
    filterColId ? { collection_id: filterColId, limit: 50 } : { limit: 50 }
  )
  const [expanded, setExpanded] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState<string | null>(null)

  async function handleCancel(jobId: string) {
    if (!confirm('Cancel this ingestion job?')) return
    setCancelling(jobId)
    try { await cancelIngestJob(jobId); refetch() }
    catch (e: any) { alert(e?.message || 'Cancel failed') }
    finally { setCancelling(null) }
  }

  async function handleDelete(jobId: string) {
    if (!confirm('Delete this ingestion job?')) return
    setDeleting(jobId)
    try { await deleteIngestJob(jobId); refetch() }
    catch (e: any) { alert(e?.message || 'Delete failed') }
    finally { setDeleting(null) }
  }

  if (loading) return <LoadingSpinner />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />

  const selectClasses = "h-8 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-semibold text-muted-foreground/70 focus:outline-none focus:ring-2 focus:ring-primary/15 focus:ring-offset-1 disabled:cursor-not-allowed appearance-none cursor-pointer transition-all duration-150"

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground/90">Ingestion Jobs</h1>
          <p className="text-sm text-muted-foreground/60 mt-1">Track document processing pipeline</p>
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-3.5 w-3.5 text-muted-foreground/50" />
          <select
            className={selectClasses}
            value={filterColId}
            onChange={e => setFilterColId(e.target.value)}
          >
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
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50">
                    <th className="pb-3 pt-4 pl-6 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Job ID</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Collection</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Source</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Progress</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Status</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Created</th>
                    <th className="pb-3 pt-4 pr-6 text-right text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {jobs.map(j => (
                    <>
                      <tr key={j.id} className="row-lift" onClick={() => setExpanded(expanded === j.id ? null : j.id)}>
                        <td className="py-3 pl-6 font-mono text-xs text-muted-foreground/70 font-medium">{j.id.slice(0, 8)}</td>
                        <td className="py-3 font-mono text-xs text-muted-foreground/70 font-medium">{j.collection_id.slice(0, 8)}</td>
                        <td className="py-3"><StatusBadge status={j.source_type} /></td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-16 rounded-full bg-muted/60 overflow-hidden">
                              <div
                                className="h-full rounded-full bg-primary/40 transition-all duration-300"
                                style={{ width: `${j.total_docs ? (j.completed_docs / j.total_docs) * 100 : 0}%` }}
                              />
                            </div>
                            <span className="text-xs text-muted-foreground/60 font-medium">{j.completed_docs}/{j.total_docs}</span>
                          </div>
                        </td>
                        <td className="py-3"><StatusBadge status={j.status} /></td>
                        <td className="py-3 text-xs text-muted-foreground/50 whitespace-nowrap font-medium">{j.created_at ? new Date(j.created_at).toLocaleDateString() : '-'}</td>
                        <td className="py-3 pr-6">
                          <div className="flex items-center justify-end gap-1">
                            {['running', 'processing', 'pending'].includes(j.status) && (
                              <Button variant="ghost" size="icon" disabled={cancelling === j.id} onClick={e => { e.stopPropagation(); handleCancel(j.id) }} className="h-8 w-8 rounded-md" title="Cancel">
                                <Square className="h-4 w-4 text-amber-500/70" strokeWidth={1.8} />
                              </Button>
                            )}
                            <Button variant="ghost" size="icon" disabled={deleting === j.id} onClick={e => { e.stopPropagation(); handleDelete(j.id) }} className="h-8 w-8 rounded-md" title="Delete">
                              <Trash2 className="h-4 w-4 text-muted-foreground/40 hover:text-destructive transition-colors" strokeWidth={1.8} />
                            </Button>
                          </div>
                        </td>
                      </tr>
                      {expanded === j.id && j.errors && j.errors.length > 0 && (
                        <tr key={`${j.id}-err`} className="bg-muted/20">
                          <td colSpan={7} className="py-3 pl-6 pr-6">
                            <pre className="text-xs text-destructive/80 whitespace-pre-wrap font-mono bg-destructive/5 rounded-lg p-3 border border-destructive/10">{JSON.stringify(j.errors, null, 2)}</pre>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
