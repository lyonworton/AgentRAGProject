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
                  ? "bg-primary/8 text-primary font-semibold border border-primary/10"
                  : "hover:bg-muted/50 text-muted-foreground/70 hover:text-foreground font-medium"
              )}
              onClick={() => { navigate('/chat/' + s.id); onClose?.() }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <MessageSquare className={cn("h-3.5 w-3.5 shrink-0", sessionId === s.id ? "text-primary/70" : "opacity-50")} strokeWidth={1.8} />
                  <span className="truncate text-sm">{s.title || 'New session'}</span>
                </div>
                <p className="text-[11px] text-muted-foreground/40 mt-0.5 ml-5 font-medium">
                  {s.message_count} message{ s.message_count !== 1 ? 's' : ''}
                </p>
              </div>
              <button
                className="opacity-0 group-hover:opacity-100 p-1 hover:text-destructive transition-all duration-150 rounded-md"
                onClick={e => { e.stopPropagation(); remove(s.id) }}
              >
                <Trash2 className="h-3.5 w-3.5" strokeWidth={1.8} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
