import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCollections } from '@/hooks/useCollections'
import { ingestLocal, ingestLocalBatch, ingestWeb, ingestDatabase } from '@/api/ingestion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { EmptyState } from '@/components/shared/EmptyState'
import { cn } from '@/lib/utils'
import { Upload, Globe, Database as DbIcon, FileText } from 'lucide-react'

type Tab = 'local' | 'web' | 'database'

export function Ingestion() {
  const { data: cols, loading } = useCollections()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('local')
  const [colId, setColId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [msg, setMsg] = useState('')

  const [files, setFiles] = useState<FileList | null>(null)
  const [selectedFiles, setSelectedFiles] = useState<{ name: string; size: number }[]>([])
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null)
  const [totalSize, setTotalSize] = useState(0)
  const [urls, setUrls] = useState('')
  const [dbUrl, setDbUrl] = useState('')
  const [dbQuery, setDbQuery] = useState('')
  const [titleCol, setTitleCol] = useState('')
  const [contentCols, setContentCols] = useState('')

  async function submit() {
    if (!colId) { setMsg('Please select a collection'); return }
    setSubmitting(true); setMsg('')
    try {
      if (tab === 'local') {
        if (!files || files.length === 0) { setMsg('Please select files'); setSubmitting(false); return }
        const fileArray = Array.from(files)

        if (fileArray.length > 5) {
          await ingestLocalBatch(colId, fileArray, (progress) => {
            setUploadProgress({ done: progress.done, total: progress.total })
          })
        } else {
          const fd = new FormData()
          fd.append('collection_id', colId)
          fileArray.forEach(f => fd.append('files', f))
          const token = localStorage.getItem('token')
          setUploadProgress({ done: 1, total: fileArray.length })
          const res = await fetch('/api/v1/ingest/local', {
            method: 'POST',
            headers: token ? { Authorization: `Bearer ${token}` } : {},
            body: fd,
          })
          if (!res.ok) throw new Error(`Ingest failed: ${res.status}`)
          await res.json()
          setUploadProgress(null)
        }
      } else if (tab === 'web') {
        const urlList = urls.split('\n').map(s => s.trim()).filter(Boolean)
        if (urlList.length === 0) { setMsg('Please enter at least one URL'); setSubmitting(false); return }
        await ingestWeb(colId, urlList)
      } else {
        if (!dbUrl || !dbQuery || !titleCol || !contentCols) { setMsg('Please fill in all fields'); setSubmitting(false); return }
        await ingestDatabase(colId, dbUrl, dbQuery, titleCol, contentCols.split(',').map(s => s.trim()))
      }
      setMsg('Submitted successfully!')
      setTimeout(() => navigate('/admin/ingestion/jobs'), 500)
    } catch (e: any) {
      setMsg(e?.message || 'Submit failed')
    } finally { setSubmitting(false) }
  }

  if (loading) return <LoadingSpinner />

  const tabs: { key: Tab; label: string; icon: typeof Upload }[] = [
    { key: 'local', label: 'Local Files', icon: Upload },
    { key: 'web', label: 'Web URLs', icon: Globe },
    { key: 'database', label: 'Database', icon: DbIcon },
  ]

  const selectClasses = "w-full h-9 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/15 focus:ring-offset-1 disabled:cursor-not-allowed appearance-none cursor-pointer transition-all duration-150"

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground/90">Data Ingestion</h1>
        <p className="text-sm text-muted-foreground/60 mt-1">Upload documents to build your knowledge base</p>
      </div>

      {/* Collection selector */}
      <div className="space-y-2">
        <Label>Select Collection</Label>
        {(!cols || cols.length === 0) ? (
          <EmptyState title="No collections found. Create one first." />
        ) : (
          <select
            className={selectClasses}
            value={colId}
            onChange={e => setColId(e.target.value)}
          >
            <option value="">-- Select a collection --</option>
            {cols.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-muted/40 rounded-lg w-fit border border-border/30">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
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

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold">{tabs.find(t => t.key === tab)?.label}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {tab === 'local' && (
            <div className="space-y-2">
              <Label>Select Files</Label>
              <Input
                type="file"
                multiple
                onChange={e => {
                  const fileList = (e.target as HTMLInputElement).files
                  setFiles(fileList)
                  if (fileList) {
                    const info = Array.from(fileList).map(f => ({ name: f.name, size: f.size }))
                    setSelectedFiles(info)
                    setTotalSize(info.reduce((sum, f) => sum + f.size, 0))
                  }
                }}
              />
              {selectedFiles.length > 0 && (
                <div className="space-y-2 mt-2 p-3.5 rounded-lg bg-muted/20 border border-border/30">
                  <p className="text-xs font-semibold text-muted-foreground/80 flex items-center gap-1.5">
                    <FileText className="h-3.5 w-3.5" />
                    {selectedFiles.length} file(s) selected
                    {totalSize > 0 && ` -- ${(totalSize / 1024 / 1024).toFixed(2)} MB`}
                  </p>
                  <div className="max-h-24 overflow-y-auto space-y-0.5">
                    {selectedFiles.map((f, i) => (
                      <p key={i} className="text-[11px] text-muted-foreground/50 truncate font-mono">{f.name} ({(f.size / 1024).toFixed(1)} KB)</p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {tab === 'web' && (
            <div className="space-y-2">
              <Label>URL List (one per line)</Label>
              <textarea
                className="w-full min-h-[120px] rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/15 focus:ring-offset-1 resize-none transition-all duration-150"
                value={urls}
                onChange={e => setUrls(e.target.value)}
                placeholder="https://example.com/article1&#10;https://example.com/article2"
              />
            </div>
          )}
          {tab === 'database' && (
            <div className="space-y-3">
              <div className="space-y-1.5"><Label>Database URL</Label><Input value={dbUrl} onChange={e => setDbUrl(e.target.value)} placeholder="postgresql://user:pass@host/db" /></div>
              <div className="space-y-1.5"><Label>SQL Query</Label><Input value={dbQuery} onChange={e => setDbQuery(e.target.value)} placeholder="SELECT * FROM articles" /></div>
              <div className="space-y-1.5"><Label>Title Column</Label><Input value={titleCol} onChange={e => setTitleCol(e.target.value)} placeholder="title" /></div>
              <div className="space-y-1.5"><Label>Content Columns (comma separated)</Label><Input value={contentCols} onChange={e => setContentCols(e.target.value)} placeholder="body,summary" /></div>
            </div>
          )}
        </CardContent>
      </Card>

      {msg && (
        <p className={cn("text-sm font-semibold", msg.includes('successfully') ? 'text-success' : 'text-destructive')}>
          {msg}
        </p>
      )}

      {uploadProgress && (
        <div className="text-xs text-muted-foreground/70 font-semibold">
          Uploading {uploadProgress.done}/{uploadProgress.total} file(s)...
        </div>
      )}

      <Button onClick={submit} disabled={submitting || !colId} className="rounded-lg">
        {submitting ? 'Submitting...' : 'Submit Ingestion Job'}
      </Button>
    </div>
  )
}
