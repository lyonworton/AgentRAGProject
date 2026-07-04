import { cn } from '@/lib/utils'
import { type ReactNode } from 'react'

interface Citation {
  document_title?: string
  title?: string
  text_snippet?: string
  text?: string
  relevance?: number
  chunk_id?: string
}

interface Props {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  citations?: Citation[]
  traceId?: string
  onCitationClick?: (c: Citation) => void
}

export function MessageBubble({ role, content, isStreaming, citations, traceId, onCitationClick }: Props) {
  const isUser = role === 'user'

  function renderContent(text: string) {
    if (!citations || citations.length === 0) return text

    // Split on [1], [2], [3], ... and replace with clickable badges
    const parts = text.split(/(\[\d+\])/g)
    return parts.map((part, i) => {
      const m = part.match(/^\[(\d+)\]$/)
      if (m) {
        const idx = parseInt(m[1]) - 1
        const cite = citations[idx]
        if (cite) {
          return (
            <span
              key={i}
              className="inline-flex items-center justify-center min-w-[1.25rem] h-5 rounded-full bg-primary/10 text-primary text-[11px] font-semibold cursor-pointer hover:bg-primary/20 transition-colors align-middle mx-0.5 px-0.5"
              onClick={() => onCitationClick?.(cite)}
              title={cite.document_title || cite.title || `Citation ${idx + 1}`}
            >
              {m[1]}
            </span>
          )
        }
      }
      return <span key={i}>{part}</span>
    })
  }

  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
          isUser
            ? 'bg-primary text-primary-foreground shadow-sm rounded-br-sm'
            : 'bg-card border border-border/50 shadow-card rounded-sm'
        )}
      >
        <div className="whitespace-pre-wrap">{renderContent(content)}</div>
        {isStreaming && (
          <span className="inline-block w-1.5 h-4 ml-0.5 rounded-sm bg-primary/50 animate-pulse align-text-bottom" />
        )}
      </div>
    </div>
  )
}
