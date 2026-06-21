import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

interface Citation {
  document_title?: string
  title?: string
  text_snippet?: string
  text?: string
  relevance?: number
  chunk_id?: string
}

interface Props {
  citations: Citation[]
  activeIndex: number | null
  onClose: () => void
}

export function CitationPanel({ citations, activeIndex, onClose }: Props) {
  return (
    <div className="w-96 border-l border-border/50 bg-card flex flex-col shrink-0 overflow-hidden shadow-[−4px_0_24px_rgba(0,0,0,0.04)]">
      <div className="h-14 flex items-center justify-between px-5 border-b border-border/40 shrink-0 bg-card/80 backdrop-blur-sm">
        <h3 className="font-semibold text-sm tracking-tight text-foreground/80">Citations ({citations.length})</h3>
        <Button variant="ghost" size="icon" onClick={onClose} className="h-7 w-7 rounded-md">
          <X className="h-4 w-4" strokeWidth={2} />
        </Button>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {citations.map((c, i) => (
          <div
            key={i}
            id={`cite-${i}`}
            className={cn(
              'p-3.5 rounded-lg border transition-all duration-150',
              activeIndex === i
                ? 'border-primary/25 bg-primary/[0.02] shadow-card ring-1 ring-primary/5'
                : 'border-border/50 hover:border-border/70'
            )}
          >
            <p className="font-medium text-sm leading-snug text-foreground/90">{c.document_title || c.title || `Citation ${i + 1}`}</p>
            <p className="text-muted-foreground/70 mt-1.5 text-xs leading-relaxed line-clamp-3">
              {c.text_snippet || c.text || 'No preview available'}
            </p>
            <div className="flex items-center gap-3 mt-2.5 text-[11px] text-muted-foreground/60 font-medium">
              {c.relevance != null && <span>Score: {c.relevance.toFixed(3)}</span>}
              {c.chunk_id && <span className="font-mono opacity-60">ID: {c.chunk_id.slice(0, 8)}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
