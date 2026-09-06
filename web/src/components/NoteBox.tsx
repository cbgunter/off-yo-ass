import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

function formatSaved(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/**
 * The always-available free-text field. Parsed server-side into standing
 * context with a type and an expiry -- this component only has to submit
 * the raw text and report back what happened. The "last saved" line is
 * sourced from the server so it survives a reload or a second device.
 */
export function NoteBox() {
  const [text, setText] = useState('')
  const [status, setStatus] = useState<'idle' | 'saving' | 'error'>('idle')
  const [lastSaved, setLastSaved] = useState<string | null>(null)

  useEffect(() => {
    api
      .get<{ when: string } | null>('/notes/latest')
      .then((res) => setLastSaved(res?.when ?? null))
      .catch(() => setLastSaved(null))
  }, [])

  const submit = async () => {
    if (!text.trim()) return
    setStatus('saving')
    try {
      await api.post('/notes', { text })
      setText('')
      setStatus('idle')
      setLastSaved(new Date().toISOString())
    } catch {
      setStatus('error')
    }
  }

  return (
    <div className="stack">
      <span className="metric-label">Tell it something</span>
      <textarea
        className="input"
        style={{ minHeight: '72px', paddingTop: 'var(--space-3)' }}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setStatus('idle')
        }}
        placeholder="Back is sore. Denver Tuesday to Thursday. Beach in six weeks."
      />
      <button
        className="btn btn-secondary"
        disabled={status === 'saving'}
        onClick={() => void submit()}
      >
        Save
      </button>
      {status === 'error' && <p className="empty-state">Could not save. Try again.</p>}
      {status !== 'error' && lastSaved && (
        <p className="timestamp">Last saved {formatSaved(lastSaved)}.</p>
      )}
    </div>
  )
}
