import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Send, StopCircle } from 'lucide-react'
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

interface ThoughtItem {
  phase: string
  text: string
  score?: number
  claims?: Array<{text: string; status: string}>
}

interface Props {
  selectedCollectionId: string
}

function ThoughtBubble({ thought }: { thought: ThoughtItem }) {
  return (
    <div className="flex justify-start my-1">
      <div className="max-w-[85%] rounded-lg px-3 py-2 bg-muted/30 border border-muted text-xs text-muted-foreground">
        <span className="font-medium text-foreground/70">{thought.phase}</span>
        <span className="mx-1">·</span>
        <span>{thought.text}</span>
        {thought.score !== undefined && (
          <span className="ml-1 text-blue-500">({(thought.score * 100).toFixed(0)}%)</span>
        )}
        {thought.claims && thought.claims.length > 0 && (
          <div className="mt-1 space-y-0.5">
            {thought.claims.map((c, i) => (
              <div key={i} className="flex gap-1">
                <span className={c.status === 'verified' ? 'text-green-500' : c.status === 'contradicted' ? 'text-red-500' : 'text-yellow-500'}>
                  {c.status === 'verified' ? '✓' : c.status === 'contradicted' ? '✗' : '?'}
                </span>
                <span className="truncate">{c.text}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function ChatView({ selectedCollectionId }: Props) {
  const { sessionId } = useParams<{ sessionId: string }>()
  const {
    messages,
    isStreaming,
    statusBar,
    thoughts,
    citations,
    error,
    timedOut,
    latencyMs,
    send,
    abort,
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

  function handleAbort() {
    abort()
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
              {!m.streaming && m.latencyMs && m.role === 'assistant' && m.content && (
                <div className="flex justify-start pl-1 text-xs text-muted-foreground/50">
                  {(m.latencyMs / 1000).toFixed(1)}s
                </div>
              )}
            </div>
          ))}
          {thoughts.map((t, i) => (
            <ThoughtBubble key={`thought-${i}`} thought={t} />
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
            {isStreaming ? (
              <Button onClick={handleAbort} variant="destructive">
                <StopCircle className="h-4 w-4" />
              </Button>
            ) : (
              <Button onClick={handleSend} disabled={!input.trim()}>
                <Send className="h-4 w-4" />
              </Button>
            )}
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