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
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <StatsCard icon={Database} label="Collections" value={cols?.length ?? 0} />
        <StatsCard icon={FileText} label="Documents" value={totalDocs} />
        <StatsCard icon={ListTodo} label="Recent Jobs" value={jobs?.length ?? 0} />
      </div>
      <Card>
        <CardHeader><CardTitle className="text-lg">Recent Jobs</CardTitle></CardHeader>
        <CardContent>
          {(!jobs || jobs.length === 0) ? (
            <p className="text-sm text-muted-foreground text-center py-8">No jobs yet</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 font-medium">Job ID</th>
                  <th className="pb-2 font-medium">Collection</th>
                  <th className="pb-2 font-medium">Source</th>
                  <th className="pb-2 font-medium">Progress</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(j => (
                  <tr key={j.id} className="border-b last:border-0">
                    <td className="py-2 font-mono text-xs">{j.id.slice(0, 8)}</td>
                    <td className="py-2 font-mono text-xs">{j.collection_id.slice(0, 8)}</td>
                    <td className="py-2"><StatusBadge status={j.source_type} /></td>
                    <td className="py-2">{j.completed_docs}/{j.total_docs}</td>
                    <td className="py-2"><StatusBadge status={j.status} /></td>
                    <td className="py-2 text-xs text-muted-foreground">{j.created_at ? new Date(j.created_at).toLocaleString() : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}