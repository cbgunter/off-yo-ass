const KNOWN_SOURCES = [
  { name: 'Garmin', note: 'sleep, HRV, resting heart rate, weight' },
  { name: 'Google Calendar', note: 'tonight, tomorrow, travel' },
  { name: 'Weather', note: 'National Weather Service, no key needed' },
  { name: 'Concept2', note: 'rowing, including ErgData' },
  { name: 'Peloton', note: 'ride and strength detail' },
]

export function Sources() {
  return (
    <div className="screen">
      <h1 className="screen-title">Sources</h1>
      <ul>
        {KNOWN_SOURCES.map((source) => (
          <li key={source.name} className="metric-row">
            <span className="metric-label">{source.name}</span>
            <div className="metric-row__figures">
              <span className="body-text" style={{ margin: 0 }}>
                {source.note}
              </span>
              <span className="timestamp">not connected</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
