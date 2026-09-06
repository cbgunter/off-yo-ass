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

type HealthData = {
  sleep: MetricPoint
  resting_heart_rate: MetricPoint
  hrv: MetricPoint
  stress: MetricPoint
  body_battery: MetricPoint
  steps: MetricPoint
  weight: MetricPoint
}

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
  key: keyof HealthData
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

export function Health() {
  const [data, setData] = useState<HealthData | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    api
      .get<HealthData>('/dashboard')
      .then(setData)
      .catch(() => setError(true))
  }, [])

  return (
    <div className="screen">
      <h1 className="screen-title">Health</h1>

      {error && <p className="empty-state">Could not load today's numbers. Try again shortly.</p>}
      {!error && !data && <p className="empty-state">Loading.</p>}

      {data && (
        <div>{METRICS.map((config) => renderMetric(config, data[config.key]))}</div>
      )}

      <hr className="hairline" />
      <NoteBox />
    </div>
  )
}
