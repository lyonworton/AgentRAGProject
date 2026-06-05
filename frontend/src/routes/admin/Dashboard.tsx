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
        <StatsCard icon={Database} label="知识库总数" value={cols?.length ?? 0} />
        <StatsCard icon={FileText} label="文档总数" value={totalDocs} />
        <StatsCard icon={ListTodo} label="最近任务" value={jobs?.length ?? 0} />
      </div>
      <Card>
        <CardHeader><CardTitle className="text-lg">最近任务</CardTitle></CardHeader>
        <CardContent>
          {(!jobs || jobs.length === 0) ? (
            <p className="text-sm text-muted-foreground text-center py-8">暂无任务</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 font-medium">Job ID</th>
                  <th className="pb-2 font-medium">知识库</th>
                  <th className="pb-2 font-medium">来源</th>
                  <th className="pb-2 font-medium">进度</th>
                  <th className="pb-2 font-medium">状态</th>
                  <th className="pb-2 font-medium">创建时间</th>
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
