import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2 } from 'lucide-react'
import { useCollections } from '@/hooks/useCollections'
import { deleteCollection } from '@/api/collections'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Collections</h1>
        <Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4 mr-1" /> New</Button>
      </div>
      <CreateCollectionDialog open={showCreate} onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); refetch() }} />
      {(!data || data.length === 0) ? (
        <EmptyState title="No collections yet. Click 'New' to create one." />
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="p-3 font-medium">Name</th>
                  <th className="p-3 font-medium">Docs</th>
                  <th className="p-3 font-medium">Chunks</th>
                  <th className="p-3 font-medium">Status</th>
                  <th className="p-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.map(c => (
                  <tr key={c.id} className="border-b last:border-0 hover:bg-muted/50 cursor-pointer" onClick={() => navigate(`/admin/collections/${c.id}`)}>
                    <td className="p-3 font-medium">{c.name}</td>
                    <td className="p-3">{c.doc_count}</td>
                    <td className="p-3">{c.chunk_count}</td>
                    <td className="p-3"><StatusBadge status={c.status} /></td>
                    <td className="p-3">
                      <Button variant="ghost" size="icon" disabled={deleting === c.id} onClick={e => { e.stopPropagation(); handleDelete(c.id) }}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
