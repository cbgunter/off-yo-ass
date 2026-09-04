import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { PushPermission } from '@/components/PushPermission'

type SourceStatus = {
  name: string
  note: string
  status: 'connected' | 'stale' | 'not_connected'
  last_synced: string | null
}

function formatTimestamp(iso: string): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(iso))
}

function statusText(source: SourceStatus): string {
  if (source.status === 'not_connected') return 'not connected'
  if (!source.last_synced) return source.status
  const prefix = source.status === 'stale' ? 'last synced' : 'synced'
  return `${prefix} ${formatTimestamp(source.last_synced)}`
}

export function Sources() {
  const [sources, setSources] = useState<SourceStatus[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    api
      .get<SourceStatus[]>('/sources')
      .then(setSources)
      .catch(() => setError(true))
  }, [])

  return (
    <div className="screen">
      <h1 className="screen-title">Sources</h1>

      {error && <p className="empty-state">Could not load sources. Try again shortly.</p>}
      {!error && !sources && <p className="empty-state">Loading.</p>}

      {sources && (
        <ul>
          {sources.map((source) => (
            <li key={source.name} className="metric-row">
              <span className="metric-label">{source.name}</span>
              <div className="metric-row__figures">
                <span className="body-text" style={{ margin: 0 }}>
                  {source.note}
                </span>
                <span className="timestamp">{statusText(source)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}

      <hr className="hairline" />
      <PushPermission />
    </div>
  )
}
