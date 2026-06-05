interface StatusEvent { phase: string; message: string }
interface ChunkEvent { text: string; citations: any[] }
interface DoneEvent { trace_id: string; citations: any[]; iterations: number; quality_score: number }

export async function fetchSSE(
  url: string,
  body: object,
  onStatus: (data: StatusEvent) => void,
  onChunk: (data: ChunkEvent) => void,
  onDone: (data: DoneEvent) => void,
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
          if (currentEvent === 'status') onStatus(data)
          else if (currentEvent === 'chunk') onChunk(data)
          else if (currentEvent === 'done') onDone(data)
        } catch { /* skip malformed JSON */ }
      }
    }
  }
}
