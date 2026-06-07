import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'

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
    <div className="w-96 border-l bg-background flex flex-col shrink-0 overflow-auto">
      <div className="h-14 flex items-center justify-between px-4 border-b shrink-0">
        <h3 className="font-medium text-sm">Citations ({citations.length})</h3>
        <Button variant="ghost" size="icon" onClick={onClose}><X className="h-4 w-4" /></Button>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {citations.map((c, i) => (
          <div
            key={i}
            id={`cite-${i}`}
            className={`p-3 rounded-md border text-sm ${activeIndex === i ? 'ring-2 ring-primary' : ''}`}
          >
            <p className="font-medium">{c.document_title || c.title || `Citation ${i + 1}`}</p>
            <p className="text-muted-foreground mt-1 text-xs">
              {(c.text_snippet || c.text || '').slice(0, 200)}
            </p>
            <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
              {c.relevance != null && <span>Relevance: {c.relevance.toFixed(3)}</span>}
              {c.chunk_id && <span className="font-mono">chunk: {c.chunk_id.slice(0, 8)}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
