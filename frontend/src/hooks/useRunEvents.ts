import { useEffect, useState } from 'react'
import { api, runEventsUrl } from '@/api/client'
import { appendEvent, parseRunEvent } from '@/api/events'
import type { RunEvent } from '@/api/types'

export function useRunEvents(id: string) {
  const [events, setEvents] = useState<RunEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [historyError, setHistoryError] = useState('')

  useEffect(() => {
    setEvents([])
    setHistoryError('')
    setConnected(false)
    let stop = false
    let source: EventSource | undefined
    void api.runHistory(id, 0).then(snapshot => {
      if (stop) return
      setEvents(snapshot.items)
      source = new EventSource(runEventsUrl(id, snapshot.next_seq - 1))
      source.onopen = () => setConnected(true)
      source.onerror = () => setConnected(false)
      for (const name of ['run.queued', 'run.started', 'run.resumed', 'run.recovered', 'run.awaiting_review', 'run.cancel_requested',
        'run.cancelled', 'run.completed', 'run.blocked', 'run.failed', 'node.started',
        'node.completed', 'node.failed', 'evidence.selected', 'plan.created', 'patch.generated',
        'verification.completed', 'review.required']) {
        source.addEventListener(name, raw => {
          const event = parseRunEvent(raw as MessageEvent<string>)
          if (event) setEvents(old => appendEvent(old, event))
        })
      }
    }).catch(e => { if (!stop) setHistoryError(e instanceof Error ? e.message : '无法读取运行事件') })
    return () => { stop = true; source?.close(); setConnected(false) }
  }, [id])

  return { events, connected, historyError }
}
