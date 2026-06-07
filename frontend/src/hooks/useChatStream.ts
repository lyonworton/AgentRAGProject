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
}

interface Citation {
  document_title?: string
  title?: string
  text_snippet?: string
  text?: string
  relevance?: number
  chunk_id?: string
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
  const [citations, setCitations] = useState<Citation[]>([])
  const [currentTraceId, setCurrentTraceId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [timedOut, setTimedOut] = useState(false)

  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Load history when session changes
  useEffect(() => {
    if (history) {
      const msgs: ChatMessage[] = history.map((m: any) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        citations: m.citations || undefined,
        traceId: m.trace_id || undefined,
      }))
      setMessages(msgs)
      setCitations([])
    } else if (!sessionId) {
      setMessages([])
      setCitations([])
    }
  }, [history, sessionId])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = useCallback(async (query: string) => {
    if (!query.trim() || isStreaming) return
    setError(null)
    setTimedOut(false)

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

    const timeoutId = setTimeout(() => {
      controller.abort()
      setTimedOut(true)
      setIsStreaming(false)
      setMessages(prev =>
        prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, streaming: false } : m,
        ),
      )
    }, 90000)

    try {
      await fetchSSE(
        '/api/v1/query/stream',
        { query, collection_ids: [selectedCollectionId], session_id: sid },
        (data: any) => setStatusBar(data.message),
        (data: any) => {
          setMessages(prev =>
            prev.map((m, i) => {
              if (i === prev.length - 1 && m.role === 'assistant') {
                return { ...m, content: m.content + data.text }
              }
              return m
            }),
          )
        },
        (data: any) => {
          setMessages(prev =>
            prev.map((m, i) => {
              if (i === prev.length - 1 && m.role === 'assistant') {
                return { ...m, streaming: false, citations: data.citations, traceId: data.trace_id }
              }
              return m
            }),
          )
          setCitations(data.citations || [])
          setCurrentTraceId(data.trace_id)
          setStatusBar(null)
          setIsStreaming(false)
        },
        controller.signal,
      )
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setError(e?.message || 'Request failed')
        setIsStreaming(false)
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
    citations,
    currentTraceId,
    error,
    timedOut,
    send,
    retry,
    bottomRef,
  }
}