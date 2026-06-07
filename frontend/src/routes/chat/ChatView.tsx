import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { StatusBar } from '@/components/chat/StatusBar'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { CitationPanel } from '@/components/chat/CitationPanel'
import { FeedbackButtons } from '@/components/chat/FeedbackButtons'
import { useChatStream } from '@/hooks/useChatStream'

interface Citation {
  document_title?: string
  title?: string
  text_snippet?: string
  text?: string
  relevance?: number
  chunk_id?: string
}

interface Props {
  selectedCollectionId: string
}

export function ChatView({ selectedCollectionId }: Props) {
  const { sessionId } = useParams<{ sessionId: string }>()
  const {
    messages,
    isStreaming,
    statusBar,
    citations,
    error,
    timedOut,
    send,
    retry,
    bottomRef,
  } = useChatStream(selectedCollectionId, sessionId)

  const [input, setInput] = useState('')
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null)
  const [showCitations, setShowCitations] = useState(false)

  function handleSend() {
    send(input)
    setInput('')
  }

  return (
    <div className="flex-1 flex">
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {!sessionId && messages.length === 0 && (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Start a conversation by typing a question
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className="space-y-1">
              <MessageBubble
                role={m.role}
                content={m.content}
                isStreaming={m.streaming}
                citations={m.citations}
                traceId={m.traceId}
                onCitationClick={(c: Citation) => { setActiveCitation(c); setShowCitations(true) }}
              />
              {!m.streaming && m.traceId && m.role === 'assistant' && (
                <div className="flex justify-start pl-1">
                  <FeedbackButtons traceId={m.traceId} />
                </div>
              )}
            </div>
          ))}
          {error && (
            <div className="text-center">
              <p className="text-sm text-destructive mb-1">{error}</p>
              {timedOut && (
                <Button variant="outline" size="sm" onClick={retry}>Retry</Button>
              )}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="px-4">
          <StatusBar message={statusBar} />
        </div>

        <div className="p-4 border-t">
          <div className="flex gap-2">
            <Input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
              placeholder="Ask a question..."
              disabled={isStreaming}
            />
            <Button onClick={handleSend} disabled={isStreaming || !input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {showCitations && citations.length > 0 && (
        <CitationPanel
          citations={citations}
          activeIndex={activeCitation ? citations.indexOf(activeCitation) : null}
          onClose={() => setShowCitations(false)}
        />
      )}
    </div>
  )
}