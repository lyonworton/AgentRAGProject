import { useNavigate, useParams } from 'react-router-dom'
import { MessageSquare, Trash2 } from 'lucide-react'
import { useSessions } from '@/hooks/useSessions'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorBanner } from '@/components/shared/ErrorBanner'
import { EmptyState } from '@/components/shared/EmptyState'
import { cn } from '@/lib/utils'

interface Props { onClose?: () => void }

export function SessionList({ onClose }: Props) {
  const { data, loading, error, refetch, remove } = useSessions()
  const navigate = useNavigate()
  const { sessionId } = useParams<{ sessionId: string }>()

  if (loading) return <div className="p-4"><LoadingSpinner text="Loading sessions..." /></div>
  if (error) return <div className="p-4"><ErrorBanner message={error} onRetry={refetch} /></div>

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-1.5 space-y-0.5">
        {(!data || data.length === 0) ? (
          <EmptyState title="No conversation history" />
        ) : (
          data.map(s => (
            <div
              key={s.id}
              className={cn(
                "group flex items-center justify-between px-3 py-2 rounded-lg text-sm cursor-pointer transition-all duration-150",
                sessionId === s.id
                  ? "bg-primary/10 text-primary font-medium border border-primary/15"
                  : "hover:bg-muted/60 text-muted-foreground/80 hover:text-foreground"
              )}
              onClick={() => { navigate('/chat/' + s.id); onClose?.() }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />
                  <span className="truncate text-sm">{s.title || 'New session'}</span>
                </div>
                <p className="text-[11px] text-muted-foreground/50 mt-0.5 ml-5.5">
                  {s.message_count} messages
                </p>
              </div>
              <button
                className="opacity-0 group-hover:opacity-100 p-1 hover:text-destructive transition-all duration-150 rounded"
                onClick={e => { e.stopPropagation(); remove(s.id) }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
