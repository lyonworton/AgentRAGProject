import { useState } from 'react'
import { ThumbsUp, ThumbsDown } from 'lucide-react'
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
    return <span className="text-xs text-muted-foreground">Submitted ✓</span>
  }

  return (
    <div className="flex items-center gap-2">
      <Button variant="ghost" size="sm" onClick={() => submit(traceId, 5, 'helpful').then(() => setLocalDone(true))}>
        <ThumbsUp className="h-4 w-4" /> Helpful
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setShowComment(!showComment)}>
        <ThumbsDown className="h-4 w-4" /> Inaccurate
      </Button>
      {showComment && (
        <div className="flex items-center gap-1">
          <input
            className="h-8 rounded-md border border-input bg-background px-2 text-xs"
            placeholder="What's inaccurate?"
            value={comment}
            onChange={e => setComment(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { submit(traceId, 1, 'inaccurate', comment).then(() => { setShowComment(false); setLocalDone(true) }) } }}
          />
          <Button size="sm" variant="outline" onClick={() => submit(traceId, 1, 'inaccurate', comment).then(() => { setShowComment(false); setLocalDone(true) })}>
            Submit
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setShowComment(false)}>Cancel</Button>
        </div>
      )}
    </div>
  )
}
