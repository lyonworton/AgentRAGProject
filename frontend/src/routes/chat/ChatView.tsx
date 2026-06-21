import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Send, StopCircle, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { StatusBar } from '@/components/chat/StatusBar'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { CitationPanel } from '@/components/chat/CitationPanel'
import { FeedbackButtons } from '@/components/chat/FeedbackButtons'
import { useChatStream } from '@/hooks/useChatStream'
import { cn } from '@/lib/utils'

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

function CollapsibleThought({ thought }: { thought: ThoughtItem }) {
  const [collapsed, setCollapsed] = useState(true)
  const verifiedCount = thought.claims?.filter(c => c.status === 'verified').length ?? 0
  const contradictedCount = thought.claims?.filter(c => c.status === 'contradicted').length ?? 0

  let badge = ''
  if (thought.score !== undefined) {
    badge = `(${(thought.score * 100).toFixed(0)}%)`
  }
  if (verifiedCount > 0 || contradictedCount > 0) {
    const counts = [`✓${verifiedCount}`]
    if (contradictedCount > 0) counts.push(`✗${contradictedCount}`)
    badge = counts.join('/') + (thought.score !== undefined ? ` · ${badge}` : '')
  }

  return (
    <div className="rounded-lg border border-border/50 overflow-hidden bg-card/60">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground/80 hover:bg-muted/40 transition-colors"
      >
        <ChevronDown
          className={cn(`h-3 w-3 transition-transform shrink-0`, collapsed ? '' : 'rotate-180')}
        />
        <span className="font-medium">{thought.phase}</span>
        {badge && <span className="ml-auto text-xs font-medium text-emerald-600">{badge}</span>}
      </button>
      {!collapsed && (
        <div className="px-3 pb-2.5 pt-1 text-xs text-muted-foreground/70 bg-muted/20 border-t border-border/30">
          <div className="pt-1.5 leading-relaxed">{thought.text}</div>
          {thought.claims && thought.claims.length > 0 && (
            <div className="mt-2 space-y-1">
              {thought.claims.map((c, i) => (
                <div key={i} className="flex gap-2">
                  <span className={cn(
                    'shrink-0 font-medium',
                    c.status === 'verified' ? 'text-emerald-600' :
                    c.status === 'contradicted' ? 'text-red-500' :
                    'text-amber-500'
                  )}>
                    {c.status === 'verified' ? '✓' : c.status === 'contradicted' ? '✗' : '?'}
                  </span>
                  <span className="leading-relaxed">{c.text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function ChatView({ selectedCollectionId }: Props) {
  const { sessionId } = useParams<{ sessionId: string }>()
  const {
    messages,
    isStreaming,
    statusBar,
    thoughts: streamThoughts,
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
    <div className="flex-1 flex min-h-0">
      <div className="flex-1 flex flex-col min-h-0 min-w-0">
        {/* Messages area */}
        <div className="flex-1 overflow-auto px-6 py-5 space-y-5">
          {!sessionId && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground/60 gap-3">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/5">
                <Send className="h-6 w-6 text-primary/40" />
              </div>
              <p className="text-sm font-medium">Start a conversation by typing a question</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={`msg-${i}`} className="space-y-2">
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
                <div className="flex justify-start pl-1 text-[11px] text-muted-foreground/40 font-medium">
                  {(m.latencyMs / 1000).toFixed(1)}s
                </div>
              )}
              {m.role === 'assistant' && m.streaming && streamThoughts.length > 0 && (
                <div className="flex flex-col gap-1.5 pl-1">
                  {streamThoughts.map((t, j) => (
                    <CollapsibleThought key={`stream-${i}-${j}`} thought={t} />
                  ))}
                </div>
              )}
              {m.role === 'assistant' && !m.streaming && m.thoughts && m.thoughts.length > 0 && (
                <div className="flex flex-col gap-1.5 pl-1">
                  {m.thoughts.map((t, j) => (
                    <CollapsibleThought key={`hist-${i}-${j}`} thought={t} />
                  ))}
                </div>
              )}
            </div>
          ))}
          {error && (
            <div className="text-center py-2">
              <p className="text-sm text-destructive/90 mb-2">{error}</p>
              {timedOut && (
                <Button variant="outline" size="sm" onClick={retry}>Try again</Button>
              )}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Status bar */}
        <div className="px-6 pb-2">
          <StatusBar message={statusBar} />
        </div>

        {/* Input bar with breathing glow */}
        <div className={cn(
          "px-6 py-4 border-t transition-shadow duration-500",
          isStreaming ? "border-primary/20 shadow-[0_-4px_20px_rgba(99,102,241,0.06)]" : "border-border/40"
        )}>
          <div className={cn(
            "flex gap-2 rounded-xl border transition-all duration-500 bg-card",
            isStreaming
              ? "border-primary/25 shadow-[0_0_20px_rgba(99,102,241,0.08)]"
              : "border-border/60 shadow-sm"
          )}>
            <Input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
              placeholder="Ask a question..."
              disabled={isStreaming}
              className={cn(
                "flex-1 border-0 bg-transparent shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 px-4 h-11",
                isStreaming && "opacity-60"
              )}
            />
            {isStreaming ? (
              <Button onClick={handleAbort} variant="destructive" size="sm" className="m-1.5 rounded-lg">
                <StopCircle className="h-4 w-4" />
              </Button>
            ) : (
              <Button onClick={handleSend} disabled={!input.trim()} size="sm" className="m-1.5 rounded-lg">
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
