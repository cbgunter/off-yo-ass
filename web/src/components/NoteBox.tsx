import { useState } from 'react'
import { api } from '@/lib/api'

/**
 * The always-available free-text field. Parsed server-side into standing
 * context with a type and an expiry -- this component only has to submit
 * the raw text and report back what happened.
 */
export function NoteBox() {
  const [text, setText] = useState('')
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  const submit = async () => {
    if (!text.trim()) return
    setStatus('saving')
    try {
      await api.post('/notes', { text })
      setText('')
      setStatus('saved')
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
      <button className="btn btn-secondary" disabled={status === 'saving'} onClick={() => void submit()}>
        Save
      </button>
      {status === 'saved' && <p className="timestamp">Saved.</p>}
      {status === 'error' && <p className="empty-state">Could not save. Try again.</p>}
    </div>
  )
}
