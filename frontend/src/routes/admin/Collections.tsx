import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2, Database } from 'lucide-react'
import { useCollections } from '@/hooks/useCollections'
import { deleteCollection } from '@/api/collections'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorBanner } from '@/components/shared/ErrorBanner'
import { EmptyState } from '@/components/shared/EmptyState'
import { CreateCollectionDialog } from './CreateCollectionDialog'

export function Collections() {
  const { data, loading, error, refetch } = useCollections()
  const navigate = useNavigate()
  const [showCreate, setShowCreate] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)

  async function handleDelete(id: string) {
    if (!confirm('Delete this collection?')) return
    setDeleting(id)
    try { await deleteCollection(id); refetch() }
    catch (e: any) { alert(e?.message || 'Delete failed') }
    finally { setDeleting(null) }
  }

  if (loading) return <LoadingSpinner />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground/90">Collections</h1>
          <p className="text-sm text-muted-foreground/60 mt-1">Manage your knowledge bases</p>
        </div>
        <Button onClick={() => setShowCreate(true)} className="rounded-lg">
          <Plus className="h-4 w-4 mr-1.5" strokeWidth={2} />
          New Collection
        </Button>
      </div>

      <CreateCollectionDialog open={showCreate} onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); refetch() }} />

      {(!data || data.length === 0) ? (
        <EmptyState title="No collections yet. Click 'New Collection' to create one." />
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50">
                    <th className="pb-3 pt-4 pl-6 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Name</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Documents</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Chunks</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Status</th>
                    <th className="pb-3 pt-4 pr-6 text-right text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {data.map(c => (
                    <tr key={c.id} className="row-lift cursor-pointer" onClick={() => navigate(`/admin/collections/${c.id}`)}>
                      <td className="py-3 pl-6 font-semibold text-foreground/80">{c.name}</td>
                      <td className="py-3 text-muted-foreground/60 font-medium text-xs">{c.doc_count}</td>
                      <td className="py-3 text-muted-foreground/60 font-medium text-xs">{c.chunk_count}</td>
                      <td className="py-3"><StatusBadge status={c.status} /></td>
                      <td className="py-3 pr-6 text-right">
                        <Button variant="ghost" size="icon" disabled={deleting === c.id} onClick={e => { e.stopPropagation(); handleDelete(c.id) }} className="h-8 w-8 rounded-md">
                          <Trash2 className="h-4 w-4 text-muted-foreground/40 hover:text-destructive transition-colors" strokeWidth={1.8} />
                        </Button>
                      </td>
                    </tr>
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
