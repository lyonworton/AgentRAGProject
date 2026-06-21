import { useState } from 'react'
import { ThumbsUp, ThumbsDown, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useSubmitFeedback } from '@/hooks/useSubmitFeedback'

interface Props {
  traceId: string
}

export function FeedbackButtons({ traceId }: Props) {
  const { submitted, submit } = useSubmitFeedback()
  const [showComment, setShowComment] = useState(false)
  const [comment, setComment] = useState('')
  const [localDone, setLocalDone] = useState(false)

  if (submitted[traceId] || localDone) {
    return <span className="text-[11px] text-muted-foreground/50 font-medium">Thank you!</span>
  }

  return (
    <div className="flex items-center gap-1">
      <Button
        variant="ghost"
        size="sm"
        className="h-7 px-2 text-xs rounded-md text-muted-foreground/70 hover:text-foreground hover:bg-muted/50 transition-all duration-150"
        onClick={() => submit(traceId, 5, 'helpful').then(() => setLocalDone(true))}
      >
        <ThumbsUp className="h-3.5 w-3.5 mr-1" strokeWidth={1.8} />
        Helpful
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-7 px-2 text-xs rounded-md text-muted-foreground/70 hover:text-foreground hover:bg-muted/50 transition-all duration-150"
        onClick={() => setShowComment(!showComment)}
      >
        <ThumbsDown className="h-3.5 w-3.5 mr-1" strokeWidth={1.8} />
        Inaccurate
      </Button>
      {showComment && (
        <div className="flex items-center gap-1.5 animate-in fade-in slide-in-from-top-1">
          <input
            className="h-7 rounded-md border border-border/60 bg-background px-2.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary/20 w-36 transition-all duration-150"
            placeholder="What's inaccurate?"
            value={comment}
            onChange={e => setComment(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                submit(traceId, 1, 'inaccurate', comment).then(() => { setShowComment(false); setLocalDone(true) })
              }
            }}
            autoFocus
          />
          <Button size="sm" variant="outline" className="h-7 px-2.5 text-xs rounded-md" onClick={() => submit(traceId, 1, 'inaccurate', comment).then(() => { setShowComment(false); setLocalDone(true) })}>
            Send
          </Button>
          <Button size="sm" variant="ghost" className="h-7 w-7 p-0 rounded-md" onClick={() => setShowComment(false)}>
            <X className="h-3.5 w-3.5" strokeWidth={1.8} />
          </Button>
        </div>
      )}
    </div>
  )
}
