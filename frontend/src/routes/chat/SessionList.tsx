import { useNavigate, useParams } from 'react-router-dom'
import { MessageSquare, Trash2 } from 'lucide-react'
import { useSessions } from '@/hooks/useSessions'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorBanner } from '@/components/shared/ErrorBanner'
import { EmptyState } from '@/components/shared/EmptyState'

interface Props { onClose?: () => void }

export function SessionList({ onClose }: Props) {
  const { data, loading, error, refetch, remove } = useSessions()
  const navigate = useNavigate()
  const { sessionId } = useParams<{ sessionId: string }>()

  if (loading) return <div className="p-4"><LoadingSpinner text="加载会话..." /></div>
  if (error) return <div className="p-4"><ErrorBanner message={error} onRetry={refetch} /></div>

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-2">
        {(!data || data.length === 0) ? (
          <EmptyState title="暂无历史会话" />
        ) : (
          <div className="space-y-1">
            {data.map(s => (
              <div
                key={s.id}
                className={`group flex items-center justify-between px-3 py-2 rounded-md text-sm cursor-pointer transition-colors ${
                  sessionId === s.id ? 'bg-primary/10 text-primary font-medium' : 'hover:bg-muted'
                }`}
                onClick={() => { navigate('/chat/' + s.id); onClose?.() }}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    <span className="truncate">{s.title || '新会话'}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5 ml-6">
                    {s.message_count} 条消息
                  </p>
                </div>
                <button
                  className="opacity-0 group-hover:opacity-100 p-1 hover:text-destructive transition-opacity"
                  onClick={e => { e.stopPropagation(); remove(s.id) }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}