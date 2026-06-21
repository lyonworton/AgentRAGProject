import { cn } from '@/lib/utils'

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
              className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary/12 text-primary text-[11px] font-semibold cursor-pointer hover:bg-primary/20 transition-colors align-middle mx-0.5"
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
          'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
          isUser
            ? 'bg-primary text-primary-foreground shadow-sm'
            : 'bg-card border border-border/60 shadow-card'
        )}
      >
        <div className="whitespace-pre-wrap">{renderContent(content)}</div>
        {isStreaming && <span className="inline-block w-1.5 h-4 ml-0.5 rounded-sm bg-primary/60 animate-pulse align-text-bottom" />}
      </div>
    </div>
  )
}
