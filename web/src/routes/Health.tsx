import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { MetricRow } from '@/components/MetricRow'
import { NoteBox } from '@/components/NoteBox'

type MetricPoint = {
  label: string
  unit: string | null
  today: number | null
  average?: number | null
  delta?: number | null
  delta_pct?: number | null
  days: number
  building: boolean
}

type BloodPressureReading = {
  systolic: number
  diastolic: number
  when: string
  delta_systolic: number | null
  delta_diastolic: number | null
}

type HealthData = {
  sleep: MetricPoint
  resting_heart_rate: MetricPoint
  hrv: MetricPoint
  stress: MetricPoint
  body_battery: MetricPoint
  steps: MetricPoint
  weight: MetricPoint
  blood_pressure: BloodPressureReading | null
}

// Manual fallback for what Garmin's daily sync doesn't (yet, reliably)
// capture as a discrete activity -- see oya/workers/sync_garmin.py's real
// Garmin activity sync, which this stays alongside rather than being
// replaced by, until that's proven against a real account.
type ActivityType = 'yard_work' | 'wood_splitting' | 'longwood_walk'

const ACTIVITIES: { type: ActivityType; label: string }[] = [
  { type: 'yard_work', label: 'Yard work' },
  { type: 'wood_splitting', label: 'Split wood' },
  { type: 'longwood_walk', label: 'Walk the garden' },
]

type LogMode = { kind: 'activity'; type: ActivityType; label: string } | { kind: 'bp' } | null

function signed(n: number, digits = 0): string {
  const sign = n > 0 ? '+' : n < 0 ? '−' : ''
  return `${sign}${Math.abs(n).toFixed(digits)}`
}

function formatMinutes(total: number): string {
  const h = Math.floor(total / 60)
  const m = Math.round(total % 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function formatMinutesDelta(delta: number): string {
  const sign = delta > 0 ? '+' : delta < 0 ? '−' : ''
  const abs = Math.abs(delta)
  const h = Math.floor(abs / 60)
  const m = Math.round(abs % 60)
  const body = h > 0 ? `${h}h ${m}m` : `${m}m`
  return `${sign}${body} vs 30d`
}

/**
 * Which way is "better" for this metric — not the same as "went up."
 * RHR, stress, and weight (a stated goal) read as better when they go
 * down; sleep, HRV, body battery, and steps read as better going up.
 */
type MetricConfig = {
  key: keyof Omit<HealthData, 'blood_pressure'>
  higherIsBetter: boolean
  formatValue: (v: number) => string
  formatDelta: (d: number) => string
  unit?: string
}

const METRICS: MetricConfig[] = [
  {
    key: 'sleep',
    higherIsBetter: true,
    formatValue: formatMinutes,
    formatDelta: formatMinutesDelta,
  },
  {
    key: 'resting_heart_rate',
    higherIsBetter: false,
    formatValue: (v) => Math.round(v).toString(),
    formatDelta: (d) => `${signed(d)} vs 30d`,
    unit: 'bpm',
  },
  {
    key: 'hrv',
    higherIsBetter: true,
    formatValue: (v) => Math.round(v).toString(),
    formatDelta: (d) => `${signed(d)} vs 30d`,
    unit: 'ms',
  },
  {
    key: 'stress',
    higherIsBetter: false,
    formatValue: (v) => Math.round(v).toString(),
    formatDelta: (d) => `${signed(d)} vs 30d`,
  },
  {
    key: 'body_battery',
    higherIsBetter: true,
    formatValue: (v) => Math.round(v).toString(),
    formatDelta: (d) => `${signed(d)} vs 30d`,
  },
  {
    key: 'steps',
    higherIsBetter: true,
    formatValue: (v) => Math.round(v).toLocaleString('en-US'),
    formatDelta: (d) => `${signed(d)} vs 30d`,
  },
  {
    key: 'weight',
    higherIsBetter: false,
    formatValue: (v) => v.toFixed(1),
    formatDelta: (d) => `${signed(d, 1)} vs 30d`,
    unit: 'lbs',
  },
]

function renderMetric(config: MetricConfig, point: MetricPoint) {
  if (point.building || point.today === null) {
    return (
      <MetricRow
        key={config.key}
        label={point.label}
        value={point.today === null ? '—' : config.formatValue(point.today)}
        unit={config.unit}
        deltaText={`building baseline, ${point.days} of 30 nights`}
      />
    )
  }

  const delta = point.delta ?? 0
  const better = config.higherIsBetter ? delta > 0 : delta < 0
  const direction = delta === 0 ? 'neutral' : better ? 'above' : 'below'

  return (
    <MetricRow
      key={config.key}
      label={point.label}
      value={config.formatValue(point.today)}
      unit={config.unit}
      deltaText={config.formatDelta(delta)}
      direction={direction}
    />
  )
}

function renderBloodPressure(bp: BloodPressureReading | null) {
  if (!bp) {
    return (
      <div className="metric-row">
        <span className="metric-label">Blood pressure</span>
        <p className="empty-state">No readings yet. Log one below.</p>
      </div>
    )
  }

  const value = `${bp.systolic}/${bp.diastolic}`
  const hasDelta = bp.delta_systolic !== null
  const deltaText = hasDelta
    ? `${signed(bp.delta_systolic!)}/${signed(bp.delta_diastolic!)} vs last`
    : undefined
  const direction =
    bp.delta_systolic === null || bp.delta_systolic === 0
      ? 'neutral'
      : bp.delta_systolic < 0
        ? 'above'
        : 'below'

  return (
    <MetricRow
      label="Blood pressure"
      value={value}
      deltaText={deltaText}
      direction={hasDelta ? direction : 'neutral'}
    />
  )
}

export function Health() {
  const [data, setData] = useState<HealthData | null>(null)
  const [error, setError] = useState(false)

  const [mode, setMode] = useState<LogMode>(null)
  const [duration, setDuration] = useState('30')
  const [systolic, setSystolic] = useState('')
  const [diastolic, setDiastolic] = useState('')
  const [saved, setSaved] = useState<string | null>(null)
  const [logError, setLogError] = useState<string | null>(null)

  useEffect(() => {
    api
      .get<HealthData>('/dashboard')
      .then(setData)
      .catch(() => setError(true))
  }, [])

  const resetLog = () => {
    setMode(null)
    setDuration('30')
    setSystolic('')
    setDiastolic('')
  }

  const openMode = (next: LogMode) => {
    setSaved(null)
    setLogError(null)
    setMode(next)
  }

  const saveActivity = async () => {
    if (mode?.kind !== 'activity') return
    setLogError(null)
    try {
      await api.post('/quicklog/activity', {
        activity_type: mode.type,
        duration_min: Number(duration),
      })
      setSaved(`${mode.label} logged.`)
      resetLog()
    } catch {
      setLogError('Could not save. Try again.')
    }
  }

  const saveBp = async () => {
    const sys = Number(systolic)
    const dia = Number(diastolic)
    if (!sys || !dia) {
      setLogError('Enter both numbers.')
      return
    }
    setLogError(null)
    try {
      await api.post('/quicklog/bp', { systolic: sys, diastolic: dia })
      setSaved('Blood pressure logged.')
      resetLog()
      // The reading just logged won't show up until the next dashboard
      // fetch -- re-fetch so it appears without a manual refresh.
      api
        .get<HealthData>('/dashboard')
        .then(setData)
        .catch(() => setError(true))
    } catch {
      setLogError('Could not save. Try again.')
    }
  }

  return (
    <div className="screen">
      <h1 className="screen-title">Health</h1>

      {error && <p className="empty-state">Could not load today's numbers. Try again shortly.</p>}
      {!error && !data && <p className="empty-state">Loading.</p>}

      {data && (
        <div>
          {METRICS.map((config) => renderMetric(config, data[config.key]))}
          {renderBloodPressure(data.blood_pressure)}
        </div>
      )}

      <hr className="hairline" />

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
            <button className="btn btn-secondary" onClick={resetLog}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={() => void saveActivity()}>
              Save
            </button>
          </div>
          {logError && <p className="empty-state">{logError}</p>}
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
            <button className="btn btn-secondary" onClick={resetLog}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={() => void saveBp()}>
              Save
            </button>
          </div>
          {logError && <p className="empty-state">{logError}</p>}
        </div>
      )}

      <hr className="hairline" />
      <NoteBox />
    </div>
  )
}
