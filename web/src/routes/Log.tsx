import { useState } from 'react'
import { api } from '@/lib/api'

type ActivityType = 'yard_work' | 'wood_splitting' | 'longwood_walk'

const ACTIVITIES: { type: ActivityType; label: string }[] = [
  { type: 'yard_work', label: 'Yard work' },
  { type: 'wood_splitting', label: 'Split wood' },
  { type: 'longwood_walk', label: 'Walk the garden' },
]

type Mode = { kind: 'activity'; type: ActivityType; label: string } | { kind: 'bp' } | null

export function Log() {
  const [mode, setMode] = useState<Mode>(null)
  const [duration, setDuration] = useState('30')
  const [systolic, setSystolic] = useState('')
  const [diastolic, setDiastolic] = useState('')
  const [saved, setSaved] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setMode(null)
    setDuration('30')
    setSystolic('')
    setDiastolic('')
  }

  const openMode = (next: Mode) => {
    setSaved(null)
    setError(null)
    setMode(next)
  }

  const saveActivity = async () => {
    if (mode?.kind !== 'activity') return
    setError(null)
    try {
      await api.post('/quicklog/activity', {
        activity_type: mode.type,
        duration_min: Number(duration),
      })
      setSaved(`${mode.label} logged.`)
      reset()
    } catch {
      setError('Could not save. Try again.')
    }
  }

  const saveBp = async () => {
    const sys = Number(systolic)
    const dia = Number(diastolic)
    if (!sys || !dia) {
      setError('Enter both numbers.')
      return
    }
    setError(null)
    try {
      await api.post('/quicklog/bp', { systolic: sys, diastolic: dia })
      setSaved('Blood pressure logged.')
      reset()
    } catch {
      setError('Could not save. Try again.')
    }
  }

  return (
    <div className="screen">
      <h1 className="screen-title">Log</h1>

      {saved && !mode && <p className="body-text">{saved}</p>}

      {!mode && (
        <div className="stack">
          {ACTIVITIES.map((a) => (
            <button
              key={a.type}
              className="btn btn-secondary"
              onClick={() => openMode({ kind: 'activity', type: a.type, label: a.label })}
            >
              {a.label}
            </button>
          ))}
          <button className="btn btn-secondary" onClick={() => openMode({ kind: 'bp' })}>
            Blood pressure
          </button>
        </div>
      )}

      {mode?.kind === 'activity' && (
        <div className="stack">
          <div>
            <label className="field-label" htmlFor="duration">
              Minutes
            </label>
            <input
              id="duration"
              className="input"
              type="number"
              inputMode="numeric"
              min="1"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            />
          </div>
          <div className="btn-row">
            <button className="btn btn-secondary" onClick={reset}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={() => void saveActivity()}>
              Save
            </button>
          </div>
          {error && <p className="empty-state">{error}</p>}
        </div>
      )}

      {mode?.kind === 'bp' && (
        <div className="stack">
          <div>
            <label className="field-label" htmlFor="systolic">
              Systolic
            </label>
            <input
              id="systolic"
              className="input"
              type="number"
              inputMode="numeric"
              value={systolic}
              onChange={(e) => setSystolic(e.target.value)}
            />
          </div>
          <div>
            <label className="field-label" htmlFor="diastolic">
              Diastolic
            </label>
            <input
              id="diastolic"
              className="input"
              type="number"
              inputMode="numeric"
              value={diastolic}
              onChange={(e) => setDiastolic(e.target.value)}
            />
          </div>
          <div className="btn-row">
            <button className="btn btn-secondary" onClick={reset}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={() => void saveBp()}>
              Save
            </button>
          </div>
          {error && <p className="empty-state">{error}</p>}
        </div>
      )}
    </div>
  )
}
