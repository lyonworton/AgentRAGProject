import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Trash2, Search } from 'lucide-react'
import { useCollection } from '@/hooks/useCollection'
import { useDocuments } from '@/hooks/useDocuments'
import { deleteDocument } from '@/api/documents'
import { deleteCollection } from '@/api/collections'
import { queryRAG } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorBanner } from '@/components/shared/ErrorBanner'
import { EmptyState } from '@/components/shared/EmptyState'

type Tab = 'docs' | 'config' | 'search'

export function CollectionDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: col, loading: cl, error: ce } = useCollection(id)
  const { data: docs, loading: dl, error: de, refetch: rDocs } = useDocuments(id)
  const [tab, setTab] = useState<Tab>('docs')
  const [delId, setDelId] = useState<string | null>(null)
  const [sq, setSq] = useState('')
  const [sr, setSr] = useState<any>(null)
  const [searching, setSearching] = useState(false)
  const navigate = useNavigate()
  const [deletingCol, setDeletingCol] = useState(false)

  async function handleDeleteDoc(docId: string) {
    if (!id || !confirm('Delete this document?')) return
    setDelId(docId)
    try { await deleteDocument(id, docId); rDocs() }
    catch (e: any) { alert(e?.message || 'Delete failed') }
    finally { setDelId(null) }
  }

  async function handleDeleteCollection() {
    if (!id || !confirm('Delete this collection and all its documents? This cannot be undone.')) return
    setDeletingCol(true)
    try { await deleteCollection(id); navigate('/') }
    catch (e: any) { alert(e?.message || 'Delete failed') }
    finally { setDeletingCol(false) }
  }

  async function handleSearch() {
    if (!id || !sq.trim()) return
    setSearching(true)
    try {
      const r = await queryRAG(sq, [id])
      setSr(r)
    } catch (e: any) {
      setSr({ error: e?.message || 'Search failed' })
    } finally { setSearching(false) }
  }

  if (cl) return <LoadingSpinner />
  if (ce) return <ErrorBanner message={ce} />
  if (!col) return <EmptyState title="Collection not found" />

  const tabs: { key: Tab; label: string }[] = [
    { key: 'docs', label: 'Documents' },
    { key: 'config', label: 'Config' },
    { key: 'search', label: 'Search Test' },
  ]

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">{col.name}</h1>
        <p className="text-sm text-muted-foreground">{col.description || 'No description'}</p>
      </div>

      <div className="flex items-center justify-between">
        <div />
        <Button variant="destructive" size="sm" disabled={deletingCol} onClick={handleDeleteCollection}>
          <Trash2 className="h-4 w-4 mr-1" /> Delete Collection
        </Button>
      </div>

      <div className="flex gap-2 border-b">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'docs' && (
        dl ? <LoadingSpinner /> :
        de ? <ErrorBanner message={de} onRetry={rDocs} /> :
        (!docs || docs.length === 0) ? <EmptyState title="No documents yet. Go to Ingestion to upload." /> :
        <table className="w-full text-sm">
          <thead><tr className="border-b text-left text-muted-foreground">
            <th className="p-2 font-medium">Title</th><th className="p-2 font-medium">Source</th>
            <th className="p-2 font-medium">Size</th><th className="p-2 font-medium">Status</th>
            <th className="p-2 font-medium">Time</th><th className="p-2 font-medium">Actions</th>
          </tr></thead>
          <tbody>{docs.map(d => (
            <tr key={d.id} className="border-b last:border-0">
              <td className="p-2 font-medium">{d.title}</td>
              <td className="p-2"><StatusBadge status={d.source_type} /></td>
              <td className="p-2 text-xs">{d.file_size ? `${(d.file_size / 1024).toFixed(1)}KB` : '-'}</td>
              <td className="p-2"><StatusBadge status={d.status} /></td>
              <td className="p-2 text-xs text-muted-foreground">{d.ingested_at ? new Date(d.ingested_at).toLocaleString() : '-'}</td>
              <td className="p-2"><Button variant="ghost" size="icon" disabled={delId === d.id} onClick={() => handleDeleteDoc(d.id)}><Trash2 className="h-4 w-4 text-destructive" /></Button></td>
            </tr>
          ))}</tbody>
        </table>
      )}

      {tab === 'config' && (
        <Card>
          <CardContent className="p-4">
            {col.config && Object.keys(col.config).length > 0 ? (
              <pre className="text-xs bg-muted p-4 rounded-md overflow-auto">{JSON.stringify(col.config, null, 2)}</pre>
            ) : (
              <p className="text-sm text-muted-foreground py-8 text-center">Not configured</p>
            )}
          </CardContent>
        </Card>
      )}

      {tab === 'search' && (
        <div className="space-y-4">
          <div className="flex gap-2">
            <Input value={sq} onChange={e => setSq(e.target.value)} placeholder="Enter test query..." onKeyDown={e => e.key === 'Enter' && handleSearch()} />
            <Button onClick={handleSearch} disabled={searching}><Search className="h-4 w-4 mr-1" />{searching ? 'Searching...' : 'Search'}</Button>
          </div>
          {sr && (
            <Card>
              <CardContent className="p-4 space-y-3">
                {sr.error ? (
                  <p className="text-sm text-destructive">{sr.error}</p>
                ) : (
                  <>
                    <div>
                      <h3 className="text-sm font-medium mb-1">Answer</h3>
                      <p className="text-sm text-muted-foreground">{sr.answer}</p>
                    </div>
                    {sr.citations?.length > 0 && (
                      <div>
                        <h3 className="text-sm font-medium mb-1">Citations ({sr.citations.length})</h3>
                        <div className="space-y-2">
                          {sr.citations.map((c: any, i: number) => (
                            <div key={i} className="text-xs bg-muted p-2 rounded">
                              <p className="font-medium">{c.document_title || c.title || `Citation ${i + 1}`}</p>
                              <p className="text-muted-foreground mt-1">{(c.text_snippet || c.text || '').slice(0, 200)}</p>
                              <p className="text-muted-foreground mt-0.5">Relevance: {typeof c.relevance === 'number' ? c.relevance.toFixed(3) : '-'}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
