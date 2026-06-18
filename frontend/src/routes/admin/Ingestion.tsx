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

type Tab = 'local' | 'web' | 'database'

export function Ingestion() {
  const { data: cols, loading } = useCollections()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('local')
  const [colId, setColId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [msg, setMsg] = useState('')

  // local
  const [files, setFiles] = useState<FileList | null>(null)
  // File selection preview
  const [selectedFiles, setSelectedFiles] = useState<{ name: string; size: number }[]>([])
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null)
  const [totalSize, setTotalSize] = useState(0)
  // web
  const [urls, setUrls] = useState('')
  // database
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

        // Use ingestLocalBatch for files > 5, otherwise use the direct fetch
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

  const tabs: { key: Tab; label: string }[] = [
    { key: 'local', label: 'Local Files' },
    { key: 'web', label: 'Web' },
    { key: 'database', label: 'Database' },
  ]

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-xl font-bold">Data Ingestion</h1>

      <div className="space-y-2">
        <Label>Select Collection</Label>
        {(!cols || cols.length === 0) ? (
          <p className="text-sm text-muted-foreground">No collections yet. Please create one first.</p>
        ) : (
          <select className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm" value={colId} onChange={e => setColId(e.target.value)}>
            <option value="">-- Select a collection --</option>
            {cols.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
      </div>

      <div className="flex gap-2 border-b">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>
            {t.label}
          </button>
        ))}
      </div>

      <Card>
        <CardContent className="p-4 space-y-4">
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
                <div className="space-y-2 mt-2">
                  <p className="text-sm font-medium">
                    {selectedFiles.length} file(s) selected
                    {totalSize > 0 && ` -- ${(totalSize / 1024 / 1024).toFixed(2)} MB`}
                  </p>
                  <div className="max-h-32 overflow-y-auto space-y-0.5">
                    {selectedFiles.map((f, i) => (
                      <p key={i} className="text-xs text-muted-foreground truncate">{f.name} ({(f.size / 1024).toFixed(1)} KB)</p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {tab === 'web' && (
            <div className="space-y-2">
              <Label>URL List (one per line)</Label>
              <textarea className="w-full min-h-[120px] rounded-md border border-input bg-background px-3 py-2 text-sm" value={urls} onChange={e => setUrls(e.target.value)} placeholder="https://example.com/article1&#10;https://example.com/article2" />
            </div>
          )}
          {tab === 'database' && (
            <div className="space-y-3">
              <div className="space-y-2"><Label>Database URL</Label><Input value={dbUrl} onChange={e => setDbUrl(e.target.value)} placeholder="postgresql://user:pass@host/db" /></div>
              <div className="space-y-2"><Label>SQL Query</Label><Input value={dbQuery} onChange={e => setDbQuery(e.target.value)} placeholder="SELECT * FROM articles" /></div>
              <div className="space-y-2"><Label>Title Column</Label><Input value={titleCol} onChange={e => setTitleCol(e.target.value)} placeholder="title" /></div>
              <div className="space-y-2"><Label>Content Columns (comma separated)</Label><Input value={contentCols} onChange={e => setContentCols(e.target.value)} placeholder="body,summary" /></div>
            </div>
          )}
        </CardContent>
      </Card>

      {msg && <p className={`text-sm ${msg.includes('successfully') ? 'text-green-600' : 'text-destructive'}`}>{msg}</p>}

      {uploadProgress && (
        <div className="text-sm text-muted-foreground">
          Uploading {uploadProgress.done}/{uploadProgress.total} file(s)...
        </div>
      )}

      <Button onClick={submit} disabled={submitting || !colId}>
        {submitting ? 'Submitting...' : 'Submit Ingestion Job'}
      </Button>
    </div>
  )
}
