import { useState, useRef, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { StatusBar } from '@/components/chat/StatusBar'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { CitationPanel } from '@/components/chat/CitationPanel'
import { FeedbackButtons } from '@/components/chat/FeedbackButtons'
import { useSessionHistory } from '@/hooks/useSessionHistory'
import { createSession } from '@/api/sessions'
import { fetchSSE } from '@/lib/sse'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  citations?: any[]
  traceId?: string
}

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
  const navigate = useNavigate()
  const { data: history } = useSessionHistory(sessionId)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [statusBar, setStatusBar] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [citations, setCitations] = useState<Citation[]>([])
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null)
  const [showCitations, setShowCitations] = useState(false)
  const [currentTraceId, setCurrentTraceId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [timedOut, setTimedOut] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (history) {
      const msgs: ChatMessage[] = history.map((m: any) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        citations: m.citations || undefined,
        traceId: m.trace_id || undefined,
      }))
      setMessages(msgs)
    } else if (!sessionId) {
      setMessages([])
      setShowCitations(false)
      setCitations([])
    }
  }, [history, sessionId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function doSend(q: string) {
    if (!q.trim() || isStreaming) return
    setError(null)
    setTimedOut(false)

    let sid = sessionId
    if (!sid) {
      try {
        const s = await createSession(selectedCollectionId, q.slice(0, 50))
        sid = s.id
        navigate('/chat/' + sid, { replace: true })
      } catch (e: any) {
        setError(e?.message || '会话创建失败')
        return
      }
    }

    const userMsg: ChatMessage = { role: 'user', content: q }
    const aiMsg: ChatMessage = { role: 'assistant', content: '', streaming: true }
    setMessages(prev => [...prev, userMsg, aiMsg])
    setIsStreaming(true)

    const controller = new AbortController()
    const timeoutId = setTimeout(() => {
      controller.abort()
      setTimedOut(true)
      setIsStreaming(false)
      setMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, streaming: false } : m))
    }, 60000)

    try {
      await fetchSSE(
        '/api/v1/query/stream',
        { query: q, collection_ids: [selectedCollectionId], session_id: sid },
        (data: any) => setStatusBar(data.message),
        (data: any) => {
          setMessages(prev => prev.map((m, i) => {
            if (i === prev.length - 1 && m.role === 'assistant') {
              return { ...m, content: m.content + data.text }
            }
            return m
          }))
        },
        (data: any) => {
          setMessages(prev => prev.map((m, i) => {
            if (i === prev.length - 1 && m.role === 'assistant') {
              return { ...m, streaming: false, citations: data.citations, traceId: data.trace_id }
            }
            return m
          }))
          setCitations(data.citations || [])
          setCurrentTraceId(data.trace_id)
          setStatusBar(null)
          setIsStreaming(false)
          if (data.citations && data.citations.length > 0) setShowCitations(true)
        },
        controller.signal,
      )
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setError(e?.message || '请求失败')
        setIsStreaming(false)
        setMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, streaming: false } : m))
      }
    } finally {
      clearTimeout(timeoutId)
    }
  }

  function handleSend() {
    doSend(input)
    setInput('')
  }

  const handleRetry = useCallback(() => {
    const lastUser = [...messages].reverse().find(m => m.role === 'user')
    if (lastUser) {
      setMessages(prev => {
        const lastIdx = prev.length - 1
        if (lastIdx >= 0 && prev[lastIdx].role === 'assistant') return prev.slice(0, -1)
        return prev
      })
      doSend(lastUser.content)
    }
  }, [messages])

  return (
    <div className="flex-1 flex">
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {!sessionId && messages.length === 0 && (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              输入问题开始对话
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
                <Button variant="outline" size="sm" onClick={handleRetry}>重试</Button>
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
              placeholder="输入问题..."
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
