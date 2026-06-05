import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCollections } from '@/hooks/useCollections'
import { ingestLocal, ingestWeb, ingestDatabase } from '@/api/ingestion'
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
  // web
  const [urls, setUrls] = useState('')
  // database
  const [dbUrl, setDbUrl] = useState('')
  const [dbQuery, setDbQuery] = useState('')
  const [titleCol, setTitleCol] = useState('')
  const [contentCols, setContentCols] = useState('')

  async function submit() {
    if (!colId) { setMsg('请选择知识库'); return }
    setSubmitting(true); setMsg('')
    try {
      if (tab === 'local') {
        if (!files || files.length === 0) { setMsg('请选择文件'); setSubmitting(false); return }
        await ingestLocal(colId, Array.from(files))
      } else if (tab === 'web') {
        const urlList = urls.split('\n').map(s => s.trim()).filter(Boolean)
        if (urlList.length === 0) { setMsg('请输入至少一个URL'); setSubmitting(false); return }
        await ingestWeb(colId, urlList)
      } else {
        if (!dbUrl || !dbQuery || !titleCol || !contentCols) { setMsg('请填写所有字段'); setSubmitting(false); return }
        await ingestDatabase(colId, dbUrl, dbQuery, titleCol, contentCols.split(',').map(s => s.trim()))
      }
      setMsg('提交成功！')
      setTimeout(() => navigate('/admin/ingestion/jobs'), 500)
    } catch (e: any) {
      setMsg(e?.message || '提交失败')
    } finally { setSubmitting(false) }
  }

  if (loading) return <LoadingSpinner />

  const tabs: { key: Tab; label: string }[] = [
    { key: 'local', label: '本地文件' },
    { key: 'web', label: '网页' },
    { key: 'database', label: '数据库' },
  ]

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-xl font-bold">数据摄入</h1>

      <div className="space-y-2">
        <Label>选择知识库</Label>
        {(!cols || cols.length === 0) ? (
          <p className="text-sm text-muted-foreground">暂无知识库，请先创建</p>
        ) : (
          <select className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm" value={colId} onChange={e => setColId(e.target.value)}>
            <option value="">-- 选择知识库 --</option>
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
              <Label>选择文件</Label>
              <Input type="file" multiple onChange={e => setFiles((e.target as HTMLInputElement).files)} />
            </div>
          )}
          {tab === 'web' && (
            <div className="space-y-2">
              <Label>URL 列表（每行一个）</Label>
              <textarea className="w-full min-h-[120px] rounded-md border border-input bg-background px-3 py-2 text-sm" value={urls} onChange={e => setUrls(e.target.value)} placeholder="https://example.com/article1&#10;https://example.com/article2" />
            </div>
          )}
          {tab === 'database' && (
            <div className="space-y-3">
              <div className="space-y-2"><Label>数据库 URL</Label><Input value={dbUrl} onChange={e => setDbUrl(e.target.value)} placeholder="postgresql://user:pass@host/db" /></div>
              <div className="space-y-2"><Label>SQL 查询</Label><Input value={dbQuery} onChange={e => setDbQuery(e.target.value)} placeholder="SELECT * FROM articles" /></div>
              <div className="space-y-2"><Label>标题列</Label><Input value={titleCol} onChange={e => setTitleCol(e.target.value)} placeholder="title" /></div>
              <div className="space-y-2"><Label>内容列（逗号分隔）</Label><Input value={contentCols} onChange={e => setContentCols(e.target.value)} placeholder="body,summary" /></div>
            </div>
          )}
        </CardContent>
      </Card>

      {msg && <p className={`text-sm ${msg.includes('成功') ? 'text-green-600' : 'text-destructive'}`}>{msg}</p>}

      <Button onClick={submit} disabled={submitting || !colId}>
        {submitting ? '提交中...' : '提交摄入任务'}
      </Button>
    </div>
  )
}
