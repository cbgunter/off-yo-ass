import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'

type SourceStatus = { name: string; status: 'connected' | 'stale' | 'not_connected' }

/**
 * Replaces the "Sources" nav tab with a small semaphore next to Sign out
 * -- Sources itself (the screen, the API, the push deep link) is
 * unchanged, this just stops giving it a whole labeled tab for something
 * you only ever glance at. Green/rust reuse the same --above/--below
 * tokens already used for metric deltas elsewhere, not new decorative
 * iconography. Renders nothing until a verdict is in, rather than
 * guessing a color.
 */
export function StatusDot() {
  const [healthy, setHealthy] = useState<boolean | null>(null)

  useEffect(() => {
    api
      .get<SourceStatus[]>('/sources')
      .then((sources) => {
        const garmin = sources.find((s) => s.name === 'Garmin')
        setHealthy(garmin ? garmin.status === 'connected' : null)
      })
      .catch(() => setHealthy(null))
  }, [])

  if (healthy === null) return null

  return (
    <Link
      to="/sources"
      aria-label={healthy ? 'Sources: Garmin connected' : 'Sources: needs attention'}
      style={{
        display: 'inline-block',
        width: 'var(--status-dot-size)',
        height: 'var(--status-dot-size)',
        borderRadius: '50%',
        background: healthy ? 'var(--above)' : 'var(--below)',
      }}
    />
  )
}
