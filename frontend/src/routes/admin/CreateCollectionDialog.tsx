import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { createCollection } from '@/api/collections'

interface Props {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

export function CreateCollectionDialog({ open, onClose, onCreated }: Props) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  if (!open) return null

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await createCollection(name, desc || undefined)
      setName(''); setDesc('')
      onCreated()
    } catch (err: any) {
      setError(err?.message || '创建失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-background rounded-lg shadow-lg w-full max-w-md p-6" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-semibold mb-4">新建知识库</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="cname">名称</Label>
            <Input id="cname" value={name} onChange={e => setName(e.target.value)} required autoFocus />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cdesc">描述</Label>
            <Input id="cdesc" value={desc} onChange={e => setDesc(e.target.value)} />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>取消</Button>
            <Button type="submit" disabled={loading}>{loading ? '创建中...' : '创建'}</Button>
          </div>
        </form>
      </div>
    </div>
  )
}
