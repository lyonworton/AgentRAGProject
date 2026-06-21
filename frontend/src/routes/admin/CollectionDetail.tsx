import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Trash2, Search, ArrowLeft } from 'lucide-react'
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
    <div className="space-y-6">
      {/* Header with back button */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate('/admin/collections')} className="h-8 px-2">
          <ArrowLeft className="h-4 w-4 mr-1" /> Back
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{col.name}</h1>
          <p className="text-sm text-muted-foreground/70 mt-0.5">{col.description || 'No description'}</p>
        </div>
        <Button variant="destructive" size="sm" disabled={deletingCol} onClick={handleDeleteCollection}>
          <Trash2 className="h-4 w-4 mr-1.5" />
          Delete
        </Button>
      </div>

      {/* Tabs as segmented controls */}
      <div className="flex gap-1 p-1 bg-muted/40 rounded-lg w-fit">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-1.5 text-xs font-medium rounded-md transition-colors ${
              tab === t.key
                ? 'bg-card text-foreground shadow-sm border border-border/60'
                : 'text-muted-foreground/70 hover:text-foreground'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'docs' && (
        dl ? <LoadingSpinner /> :
        de ? <ErrorBanner message={de} onRetry={rDocs} /> :
        (!docs || docs.length === 0) ? <EmptyState title="No documents yet. Go to Ingestion to upload." /> :
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/60">
                    <th className="pb-3 pt-4 pl-6 text-left text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Title</th>
                    <th className="pb-3 pt-4 text-left text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Source</th>
                    <th className="pb-3 pt-4 text-left text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Size</th>
                    <th className="pb-3 pt-4 text-left text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Status</th>
                    <th className="pb-3 pt-4 text-left text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Ingested</th>
                    <th className="pb-3 pt-4 pr-6 text-right text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {docs.map(d => (
                    <tr key={d.id} className="row-lift">
                      <td className="py-3 pl-6 font-medium">{d.title}</td>
                      <td className="py-3"><StatusBadge status={d.source_type} /></td>
                      <td className="py-3 text-xs text-muted-foreground/70">{d.file_size ? `${(d.file_size / 1024).toFixed(1)}KB` : '-'}</td>
                      <td className="py-3"><StatusBadge status={d.status} /></td>
                      <td className="py-3 text-xs text-muted-foreground/50 whitespace-nowrap">{d.ingested_at ? new Date(d.ingested_at).toLocaleDateString() : '-'}</td>
                      <td className="py-3 pr-6 text-right">
                        <Button variant="ghost" size="icon" disabled={delId === d.id} onClick={() => handleDeleteDoc(d.id)} className="h-8 w-8">
                          <Trash2 className="h-4 w-4 text-muted-foreground/50 hover:text-destructive transition-colors" />
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

      {tab === 'config' && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            {col.config && Object.keys(col.config).length > 0 ? (
              <pre className="text-xs bg-muted/50 p-4 rounded-lg overflow-auto font-mono border border-border/30">{JSON.stringify(col.config, null, 2)}</pre>
            ) : (
              <p className="text-sm text-muted-foreground/60 py-4 text-center">Not configured</p>
            )}
          </CardContent>
        </Card>
      )}

      {tab === 'search' && (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Test Query</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input value={sq} onChange={e => setSq(e.target.value)} placeholder="Enter test query..." onKeyDown={e => e.key === 'Enter' && handleSearch()} className="flex-1" />
                <Button onClick={handleSearch} disabled={searching}>
                  <Search className="h-4 w-4 mr-1.5" />
                  {searching ? 'Searching...' : 'Search'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {sr && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Results</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {sr.error ? (
                  <p className="text-sm text-destructive/90">{sr.error}</p>
                ) : (
                  <>
                    <div>
                      <h3 className="text-xs font-medium text-muted-foreground/70 uppercase tracking-wider mb-1.5">Answer</h3>
                      <p className="text-sm leading-relaxed text-muted-foreground/90">{sr.answer}</p>
                    </div>
                    {sr.citations?.length > 0 && (
                      <div>
                        <h3 className="text-xs font-medium text-muted-foreground/70 uppercase tracking-wider mb-2">Citations ({sr.citations.length})</h3>
                        <div className="space-y-2">
                          {sr.citations.map((c: any, i: number) => (
                            <div key={i} className="text-xs bg-muted/30 p-3 rounded-lg border border-border/30">
                              <p className="font-medium text-sm">{c.document_title || c.title || `Citation ${i + 1}`}</p>
                              <p className="text-muted-foreground/70 mt-1 leading-relaxed">{(c.text_snippet || c.text || '').slice(0, 200)}</p>
                              <p className="text-muted-foreground/50 mt-1.5 text-[11px]">Relevance: {typeof c.relevance === 'number' ? c.relevance.toFixed(3) : '-'}</p>
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
