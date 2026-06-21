import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Trash2, Search, ArrowLeft, FileText, Settings, TestTube } from 'lucide-react'
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
import { cn } from '@/lib/utils'

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
    try { await deleteCollection(id); navigate('/admin/collections') }
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

  const tabs: { key: Tab; label: string; icon: typeof FileText }[] = [
    { key: 'docs', label: 'Documents', icon: FileText },
    { key: 'config', label: 'Config', icon: Settings },
    { key: 'search', label: 'Search Test', icon: TestTube },
  ]

  return (
    <div className="space-y-6">
      {/* Header with back button */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate('/admin/collections')} className="h-8 px-2 rounded-lg">
          <ArrowLeft className="h-4 w-4 mr-1.5" strokeWidth={2} />
          Back
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-bold tracking-tight text-foreground/90 truncate">{col.name}</h1>
          {col.description && <p className="text-sm text-muted-foreground/60 mt-0.5">{col.description}</p>}
        </div>
        <Button variant="destructive" size="sm" disabled={deletingCol} onClick={handleDeleteCollection} className="rounded-lg">
          <Trash2 className="h-4 w-4 mr-1.5" strokeWidth={1.8} />
          Delete
        </Button>
      </div>

      {/* Tabs as segmented controls */}
      <div className="flex gap-1 p-1 bg-muted/40 rounded-lg w-fit border border-border/30">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setSr(null) }}
            className={cn(
              "flex items-center gap-2 px-4 py-1.5 text-xs font-semibold rounded-md transition-all duration-150",
              tab === t.key
                ? "bg-card text-foreground shadow-sm border border-border/60"
                : "text-muted-foreground/60 hover:text-foreground hover:bg-muted/50"
            )}
          >
            <t.icon className="h-3.5 w-3.5" strokeWidth={1.8} />
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
                  <tr className="border-b border-border/50">
                    <th className="pb-3 pt-4 pl-6 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Title</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Source</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Size</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Status</th>
                    <th className="pb-3 pt-4 text-left text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Ingested</th>
                    <th className="pb-3 pt-4 pr-6 text-right text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {docs.map(d => (
                    <tr key={d.id} className="row-lift">
                      <td className="py-3 pl-6 font-medium text-foreground/80">{d.title}</td>
                      <td className="py-3"><StatusBadge status={d.source_type} /></td>
                      <td className="py-3 text-xs text-muted-foreground/50 font-medium">{d.file_size ? `${(d.file_size / 1024).toFixed(1)} KB` : '-'}</td>
                      <td className="py-3"><StatusBadge status={d.status} /></td>
                      <td className="py-3 text-xs text-muted-foreground/50 whitespace-nowrap font-medium">{d.ingested_at ? new Date(d.ingested_at).toLocaleDateString() : '-'}</td>
                      <td className="py-3 pr-6 text-right">
                        <Button variant="ghost" size="icon" disabled={delId === d.id} onClick={() => handleDeleteDoc(d.id)} className="h-8 w-8 rounded-md">
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

      {tab === 'config' && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold">Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            {col.config && Object.keys(col.config).length > 0 ? (
              <pre className="text-xs bg-muted/30 p-4 rounded-lg overflow-auto font-mono border border-border/30 text-muted-foreground/80">{JSON.stringify(col.config, null, 2)}</pre>
            ) : (
              <p className="text-sm text-muted-foreground/50 py-4 text-center">Not configured</p>
            )}
          </CardContent>
        </Card>
      )}

      {tab === 'search' && (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">Test Query</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input value={sq} onChange={e => setSq(e.target.value)} placeholder="Enter test query..." onKeyDown={e => e.key === 'Enter' && handleSearch()} className="flex-1 rounded-lg" />
                <Button onClick={handleSearch} disabled={searching} className="rounded-lg">
                  <Search className="h-4 w-4 mr-1.5" strokeWidth={1.8} />
                  {searching ? 'Searching...' : 'Search'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {sr && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold">Results</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {sr.error ? (
                  <p className="text-sm text-destructive/80 font-medium">{sr.error}</p>
                ) : (
                  <>
                    <div>
                      <h3 className="text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider mb-2">Answer</h3>
                      <p className="text-sm leading-relaxed text-muted-foreground/80">{sr.answer}</p>
                    </div>
                    {sr.citations?.length > 0 && (
                      <div>
                        <h3 className="text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider mb-2">Citations ({sr.citations.length})</h3>
                        <div className="space-y-2">
                          {sr.citations.map((c: any, i: number) => (
                            <div key={i} className="text-sm bg-muted/20 p-3.5 rounded-lg border border-border/30">
                              <p className="font-semibold text-sm leading-snug">{c.document_title || c.title || `Citation ${i + 1}`}</p>
                              <p className="text-muted-foreground/70 mt-1.5 text-xs leading-relaxed">{(c.text_snippet || c.text || '').slice(0, 200)}</p>
                              <p className="text-muted-foreground/50 mt-2 text-[11px] font-medium">Relevance: {typeof c.relevance === 'number' ? c.relevance.toFixed(3) : '-'}</p>
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
