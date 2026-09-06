import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

type Prescription = {
  activity: string
  duration_min: number
  intensity: string
  window: string
}

type Call = {
  headline: string
  prescription: Prescription
  why: string
  fallback: string
  skip_ok: boolean
  overridden: boolean
}

const ACTIVITY_LABELS: Record<string, string> = {
  peloton_ride: 'Peloton ride',
  peloton_strength: 'Peloton strength',
  row_c2: 'Row (Concept2)',
  bike_trail: 'Trail bike',
  hike: 'Hike',
  walk: 'Walk',
  yard_work: 'Yard work',
  wood_splitting: 'Split wood',
  longwood_walk: 'Walk the garden',
  golf_walk: 'Walk the course',
  mobility: 'Mobility',
  rest: 'Rest',
}

const SKIP_REASONS: { value: string; label: string }[] = [
  { value: 'too_tired', label: 'Too tired' },
  { value: 'no_time', label: 'No time' },
  { value: 'travelling', label: 'Travelling' },
  { value: 'weather', label: 'Weather' },
  { value: 'didnt_feel_like_it', label: "Didn't feel like it" },
  { value: 'something_hurt', label: 'Something hurt' },
]

type Bedtime = { body: string }

type CheckinResult = 'did_it' | 'partial' | 'no'
type Feeling = 'easy' | 'about_right' | 'brutal'

// did_it needs a feel tap only. partial needs a skip reason (something
// kept it short) AND a feel tap (it still happened). no needs a skip
// reason only -- nothing to rate the feel of.
type Stage = 'call' | 'awaiting_skip_reason' | 'awaiting_feel' | 'done'

export function TheCall() {
  const [call, setCall] = useState<Call | null | undefined>(undefined)
  const [bedtime, setBedtime] = useState<Bedtime | null>(null)
  const [error, setError] = useState(false)
  const [stage, setStage] = useState<Stage>('call')
  const [pendingResult, setPendingResult] = useState<CheckinResult | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api
      .get<Call | null>('/call/today')
      .then(setCall)
      .catch(() => setError(true))
    api
      .get<Bedtime | null>('/call/bedtime')
      .then(setBedtime)
      .catch(() => setBedtime(null))
  }, [])

  const pickResult = (value: CheckinResult) => {
    if (value === 'did_it') {
      setBusy(true)
      api
        .post('/call/checkin', { result: value })
        .then(() => setStage('awaiting_feel'))
        .finally(() => setBusy(false))
      return
    }
    setPendingResult(value)
    setStage('awaiting_skip_reason')
  }

  const pickSkipReason = async (reason: string) => {
    if (!pendingResult) return
    setBusy(true)
    try {
      await api.post('/call/checkin', { result: pendingResult, skip_reason: reason })
      setStage(pendingResult === 'partial' ? 'awaiting_feel' : 'done')
    } finally {
      setBusy(false)
    }
  }

  const pickFeel = async (value: Feeling) => {
    setBusy(true)
    try {
      await api.post('/call/feel', { feel: value })
      setStage('done')
    } finally {
      setBusy(false)
    }
  }

  const notTonight = async () => {
    setBusy(true)
    try {
      await api.post('/call/not-tonight')
      setStage('done')
    } finally {
      setBusy(false)
    }
  }

  const giveMeSomethingElse = async () => {
    setBusy(true)
    try {
      const next = await api.post<Call>('/call/override')
      setCall(next)
      setStage('call')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="screen">
      <h1 className="screen-title">The call</h1>

      {error && <p className="empty-state">Could not load tonight's call. Try again shortly.</p>}
      {call === undefined && !error && <p className="empty-state">Loading.</p>}
      {call === null && <p className="empty-state">No call yet. Check back at 15:45.</p>}

      {call && (
        <div className="stack">
          <p className="headline">{call.headline}</p>

          {!call.skip_ok && (
            <div className="prescription">
              {ACTIVITY_LABELS[call.prescription.activity] ?? call.prescription.activity}
              {', '}
              {call.prescription.duration_min} min, {call.prescription.intensity},{' '}
              {call.prescription.window}
            </div>
          )}

          <p className="body-text">{call.why}</p>

          <hr className="hairline" />
          <p className="timestamp">{call.fallback}</p>

          {stage === 'call' && (
            <>
              <div className="btn-row">
                {(['did_it', 'partial', 'no'] as CheckinResult[]).map((value) => (
                  <button
                    key={value}
                    className="btn btn-choice"
                    disabled={busy}
                    onClick={() => pickResult(value)}
                  >
                    {value === 'did_it' ? 'Did it' : value === 'partial' ? 'Partial' : 'No'}
                  </button>
                ))}
              </div>

              <div className="btn-row">
                <button
                  className="btn btn-secondary"
                  disabled={busy}
                  onClick={() => void notTonight()}
                >
                  Not tonight
                </button>
                <button
                  className="btn btn-secondary"
                  disabled={busy}
                  onClick={() => void giveMeSomethingElse()}
                >
                  Give me something else
                </button>
              </div>
            </>
          )}

          {stage === 'awaiting_skip_reason' && (
            <div className="stack">
              <p className="body-text">Why not?</p>
              <div className="btn-row" style={{ flexWrap: 'wrap' }}>
                {SKIP_REASONS.map((reason) => (
                  <button
                    key={reason.value}
                    className="btn btn-choice"
                    disabled={busy}
                    onClick={() => void pickSkipReason(reason.value)}
                  >
                    {reason.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {stage === 'awaiting_feel' && (
            <div className="stack">
              <p className="body-text">How did it feel?</p>
              <div className="btn-row">
                {(['easy', 'about_right', 'brutal'] as Feeling[]).map((value) => (
                  <button
                    key={value}
                    className="btn btn-choice"
                    disabled={busy}
                    onClick={() => void pickFeel(value)}
                  >
                    {value === 'easy' ? 'Easy' : value === 'about_right' ? 'About right' : 'Brutal'}
                  </button>
                ))}
              </div>
            </div>
          )}

          {stage === 'done' && <p className="body-text">Logged.</p>}
        </div>
      )}

      {bedtime && (
        <>
          <hr className="hairline" />
          <p className="field-label">Tonight</p>
          <p className="body-text">{bedtime.body}</p>
        </>
      )}
    </div>
  )
}
