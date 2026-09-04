type Direction = 'above' | 'below' | 'neutral'

type MetricRowProps = {
  label: string
  value: string
  unit?: string
  deltaText?: string
  direction?: Direction
}

/**
 * The base unit of the design system (BRANDING.md § Components): label
 * above, a big tabular-mono number, an optional delta against baseline.
 * Separated from its siblings by a hairline, never a card.
 */
export function MetricRow({ label, value, unit, deltaText, direction = 'neutral' }: MetricRowProps) {
  const deltaClass =
    direction === 'above' ? 'delta delta--above' : direction === 'below' ? 'delta delta--below' : 'delta'

  return (
    <div className="metric-row">
      <span className="metric-label">{label}</span>
      <div className="metric-row__figures">
        <span className="metric-value">
          {value}
          {unit && <span className="timestamp"> {unit}</span>}
        </span>
        {deltaText && <span className={deltaClass}>{deltaText}</span>}
      </div>
    </div>
  )
}
