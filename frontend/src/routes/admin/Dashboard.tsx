import { Database, FileText, ListTodo } from 'lucide-react'
import { useCollections } from '@/hooks/useCollections'
import { useIngestionJobs } from '@/hooks/useIngestionJobs'
import { StatsCard } from '@/components/shared/StatsCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorBanner } from '@/components/shared/ErrorBanner'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'

export function Dashboard() {
  const { data: cols, loading: cl, error: ce, refetch: rCols } = useCollections()
  const { data: jobs, loading: jl, error: je, refetch: rJobs } = useIngestionJobs({ limit: 10 })

  if (cl || jl) return <LoadingSpinner />
  if (ce) return <ErrorBanner message={ce} onRetry={rCols} />
  if (je) return <ErrorBanner message={je} onRetry={rJobs} />

  const totalDocs = cols?.reduce((s, c) => s + c.doc_count, 0) ?? 0

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground/70 mt-1">Overview of your knowledge base</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatsCard icon={Database} label="Collections" value={cols?.length ?? 0} />
        <StatsCard icon={FileText} label="Documents" value={totalDocs} />
        <StatsCard icon={ListTodo} label="Recent Jobs" value={jobs?.length ?? 0} />
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Recent Jobs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {(!jobs || jobs.length === 0) ? (
            <p className="text-sm text-muted-foreground/60 text-center py-10">No jobs yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/60">
                    <th className="pb-3 pt-4 pl-6 text-left text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Job ID</th>
                    <th className="pb-3 pt-4 text-left text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Collection</th>
                    <th className="pb-3 pt-4 text-left text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Source</th>
                    <th className="pb-3 pt-4 text-left text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Progress</th>
                    <th className="pb-3 pt-4 text-left text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Status</th>
                    <th className="pb-3 pt-4 pr-6 text-right text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {jobs.map(j => (
                    <tr key={j.id} className="row-lift">
                      <td className="py-3 pl-6 font-mono text-xs text-muted-foreground/80">{j.id.slice(0, 8)}</td>
                      <td className="py-3 font-mono text-xs text-muted-foreground/80">{j.collection_id.slice(0, 8)}</td>
                      <td className="py-3"><StatusBadge status={j.source_type} /></td>
                      <td className="py-3 text-muted-foreground/70">{j.completed_docs}/{j.total_docs}</td>
                      <td className="py-3"><StatusBadge status={j.status} /></td>
                      <td className="py-3 pr-6 text-right text-xs text-muted-foreground/50 whitespace-nowrap">
                        {j.created_at ? new Date(j.created_at).toLocaleDateString() : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
