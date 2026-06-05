import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Menu, Plus, MessageSquare, LayoutDashboard } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SessionList } from './SessionList'
import { ChatView } from './ChatView'
import { useCollections } from '@/hooks/useCollections'

export function ChatLayout() {
  const [showSidebar, setShowSidebar] = useState(false)
  const { data: cols } = useCollections()
  const [selectedColId, setSelectedColId] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    if (cols && cols.length > 0 && !selectedColId) {
      setSelectedColId(cols[0].id)
    }
  }, [cols, selectedColId])

  return (
    <div className="flex h-screen">
      <div className={`${showSidebar ? 'flex' : 'hidden'} md:flex w-72 border-r bg-muted/30 flex-col shrink-0`}>
        <div className="h-14 flex items-center justify-between px-4 border-b shrink-0">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            <span className="font-bold text-lg">AgentRAG</span>
          </div>
          <Button variant="ghost" size="icon" onClick={() => setShowSidebar(false)} className="md:hidden">
            <Menu className="h-4 w-4" />
          </Button>
        </div>
        <div className="p-3 border-b shrink-0">
          {(!cols || cols.length === 0) ? (
            <p className="text-xs text-muted-foreground">{'请先在 Admin 创建知识库'}</p>
          ) : (
            <select className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm" value={selectedColId} onChange={e => setSelectedColId(e.target.value)}>
              {cols.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
        </div>
        <div className="p-2 border-b shrink-0">
          <Button variant="outline" size="sm" className="w-full" onClick={() => navigate('/chat')}>
            <Plus className="h-4 w-4 mr-1" /> {'新会话'}
          </Button>
        </div>
        <SessionList onClose={() => setShowSidebar(false)} />
      </div>
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b flex items-center px-4 shrink-0">
          <Button variant="ghost" size="icon" onClick={() => setShowSidebar(true)} className="md:hidden mr-2">
            <Menu className="h-4 w-4" />
          </Button>
          <span className="font-medium text-sm">{'对话'}</span>
          <div className="flex-1" />
          <Link to="/admin" className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors">
            <LayoutDashboard className="h-3.5 w-3.5" />
            {'管理'}
          </Link>
        </header>
        <ChatView selectedCollectionId={selectedColId} />
      </div>
    </div>
  )
}
