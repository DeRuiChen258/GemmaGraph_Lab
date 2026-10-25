import type { RunEvent } from './types'

export function parseRunEvent(raw: MessageEvent<string>): RunEvent | null {
  try {
    const event = JSON.parse(raw.data) as RunEvent
    if (!event || typeof event.seq !== 'number' || typeof event.run_id !== 'string' || typeof event.type !== 'string') return null
    return event
  } catch { return null }
}

export function appendEvent(items: RunEvent[], event: RunEvent) {
  if (items.some(item => item.seq === event.seq)) return items
  return [...items, event].sort((a, b) => a.seq - b.seq).slice(-500)
}
