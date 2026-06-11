interface StatusEvent { phase: string; message: string; iteration: number }
interface ThoughtEvent { phase: string; text: string; score?: number; claims?: Array<{text: string; status: string}> }
interface ChunkEvent { text: string; citations: any[] }
interface DoneEvent { trace_id: string; answer: string; citations: any[]; iterations: number; quality_score: number; timed_out?: boolean; latency_ms?: number }
interface TimeoutEvent { message: string; trace_id: string }

export interface SSECallbacks {
  onStatus: (data: StatusEvent) => void
  onThought: (data: ThoughtEvent) => void
  onChunk: (data: ChunkEvent) => void
  onDone: (data: DoneEvent) => void
  onTimeout: (data: TimeoutEvent) => void
}

export async function fetchSSE(
  url: string,
  body: object,
  callbacks: SSECallbacks,
  signal: AbortSignal,
): Promise<void> {
  const token = localStorage.getItem('token')
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }

  const reader = res.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const dataStr = line.slice(6)
        try {
          const data = JSON.parse(dataStr)
          switch (currentEvent) {
            case 'status': callbacks.onStatus(data); break
            case 'thought': callbacks.onThought(data); break
            case 'chunk': callbacks.onChunk(data); break
            case 'done': callbacks.onDone(data); break
            case 'timeout': callbacks.onTimeout(data); break
          }
        } catch { /* skip malformed JSON */ }
      }
    }
  }
}