import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessionHistory } from '@/hooks/useSessionHistory'
import { createSession } from '@/api/sessions'
import { fetchSSE } from '@/lib/sse'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  citations?: any[]
  traceId?: string
  latencyMs?: number
  thoughts?: ThoughtItem[]
}

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

export function useChatStream(
  selectedCollectionId: string,
  sessionId: string | undefined,
) {
  const navigate = useNavigate()
  const { data: history } = useSessionHistory(sessionId)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [statusBar, setStatusBar] = useState<string | null>(null)
  const [thoughts, setThoughts] = useState<ThoughtItem[]>([])
  const [citations, setCitations] = useState<Citation[]>([])
  const [currentTraceId, setCurrentTraceId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [timedOut, setTimedOut] = useState(false)
  const [latencyMs, setLatencyMs] = useState<number | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const streamingRef = useRef(false)  // guard against history wipe during streaming
  const thoughtsRef = useRef<ThoughtItem[]>([])  // live reference for SSE callbacks (avoids stale closure)

  // Load history when session changes (skip while streaming to avoid race)
  useEffect(() => {
    if (streamingRef.current) return  // don't override streaming messages
    if (history) {
      const msgs: ChatMessage[] = history.map((m: any) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        citations: m.citations || undefined,
        traceId: m.trace_id || undefined,
        thoughts: m.thoughts || undefined,
      }))
      setMessages(msgs)
      // Restore global citations from the last assistant message for CitationPanel
      const lastAssistant = [...msgs].reverse().find((m: ChatMessage) => m.role === 'assistant')
      setCitations(lastAssistant?.citations || [])
      setThoughts([])
    } else if (!sessionId) {
      setMessages([])
      setCitations([])
      setThoughts([])
    }
  }, [history, sessionId])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thoughts])

  const send = useCallback(async (query: string) => {
    if (!query.trim() || isStreaming) return
    setError(null)
    setTimedOut(false)
    setThoughts([])
    thoughtsRef.current = []
    setLatencyMs(null)
    streamingRef.current = true

    let sid = sessionId
    if (!sid) {
      try {
        const s = await createSession(selectedCollectionId, query.slice(0, 50))
        sid = s.id
        navigate('/chat/' + sid, { replace: true })
      } catch (e: any) {
        setError(e?.message || 'Failed to create session')
        return
      }
    }

    const userMsg: ChatMessage = { role: 'user', content: query }
    const aiMsg: ChatMessage = { role: 'assistant', content: '', streaming: true }
    setMessages(prev => [...prev, userMsg, aiMsg])
    setIsStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    // 180s client-side timeout (matches backend timeout)
    const timeoutId = setTimeout(() => {
      controller.abort()
      setTimedOut(true)
      setIsStreaming(false)
      streamingRef.current = false
      setStatusBar(null)
      setMessages(prev =>
        prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, streaming: false, content: m.content || '(request timed out)' } : m,
        ),
      )
    }, 180000)

    try {
      await fetchSSE(
        '/api/v1/query/stream',
        { query, collection_ids: [selectedCollectionId], session_id: sid, options: { timeout: 180 } },
        {
          onStatus: (data: any) => setStatusBar(data.message),
          onThought: (data: any) => {
            setThoughts(prev => {
              const updated = [...prev, data]
              thoughtsRef.current = updated
              return updated
            })
          },
          onChunk: (data: any) => {
            setMessages(prev =>
              prev.map((m, i) => {
                if (i === prev.length - 1 && m.role === 'assistant') {
                  return { ...m, content: m.content + data.text }
                }
                return m
              }),
            )
          },
          onDone: (data: any) => {
            // Persist stream thoughts into the message, then clear the global streamThoughts
            // to prevent duplicate rendering (saved thoughts + stream thoughts would both show).
            // Use thoughtsRef.current instead of thoughts closure to avoid stale state.
            const savedThoughts = thoughtsRef.current.length > 0 ? [...thoughtsRef.current] : undefined
            setThoughts([])
            thoughtsRef.current = []
            setMessages(prev =>
              prev.map((m, i) => {
                if (i === prev.length - 1 && m.role === 'assistant') {
                  return {
                    ...m,
                    content: data.answer || m.content,
                    streaming: false,
                    citations: data.citations,
                    traceId: data.trace_id,
                    latencyMs: data.latency_ms,
                    thoughts: savedThoughts,
                  }
                }
                return m
              }),
            )
            setCitations(data.citations || [])
            setCurrentTraceId(data.trace_id)
            setLatencyMs(data.latency_ms || null)
            setStatusBar(null)
            setIsStreaming(false)
            streamingRef.current = false
          },
          onTimeout: (data: any) => {
            setThoughts([])
            setMessages(prev =>
              prev.map((m, i) => {
                if (i === prev.length - 1 && m.role === 'assistant') {
                  return { ...m, streaming: false }
                }
                return m
              }),
            )
            setTimedOut(true)
            setStatusBar(null)
            setIsStreaming(false)
            streamingRef.current = false
          },
        },
        controller.signal,
      )
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setError(e?.message || 'Request failed')
        setIsStreaming(false)
        streamingRef.current = false
        setMessages(prev =>
          prev.map((m, i) =>
            i === prev.length - 1 ? { ...m, streaming: false } : m,
          ),
        )
      }
    } finally {
      clearTimeout(timeoutId)
      abortRef.current = null
    }
  }, [isStreaming, selectedCollectionId, sessionId, navigate])

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setIsStreaming(false)
    streamingRef.current = false
    setStatusBar(null)
    setMessages(prev =>
      prev.map((m, i) =>
        i === prev.length - 1 && m.role === 'assistant' ? { ...m, streaming: false } : m,
      ),
    )
  }, [])

  const retry = useCallback(() => {
    const lastUser = [...messages].reverse().find(m => m.role === 'user')
    if (lastUser) {
      setMessages(prev => {
        const lastIdx = prev.length - 1
        if (lastIdx >= 0 && prev[lastIdx].role === 'assistant') return prev.slice(0, -1)
        return prev
      })
      send(lastUser.content)
    }
  }, [messages, send])

  return {
    messages,
    isStreaming,
    statusBar,
    thoughts,
    citations,
    currentTraceId,
    error,
    timedOut,
    latencyMs,
    send,
    abort,
    retry,
    bottomRef,
  }
}