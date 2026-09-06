import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Health } from './Health'

// vi.mock factories are hoisted above the rest of the file, so a fixture
// referenced inside one has to go through vi.hoisted rather than a plain
// top-level const — otherwise it's a "used before initialization" error.
const { DATA, mockGet, mockPost } = vi.hoisted(() => ({
  DATA: {
    sleep: { label: 'Sleep', unit: 'min', today: null, days: 0, building: true },
    resting_heart_rate: {
      label: 'Resting heart rate',
      unit: 'bpm',
      today: 68,
      average: 60,
      delta: 8,
      delta_pct: 13.3,
      days: 30,
      building: false,
    },
    hrv: { label: 'HRV', unit: 'ms', today: null, days: 5, building: true },
    stress: { label: 'Stress', unit: null, today: null, days: 0, building: true },
    body_battery: { label: 'Body battery', unit: null, today: null, days: 0, building: true },
    steps: { label: 'Steps', unit: null, today: null, days: 0, building: true },
    weight: { label: 'Weight', unit: 'lbs', today: null, days: 0, building: true },
  },
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: { get: mockGet, post: mockPost },
}))

beforeEach(() => {
  mockGet.mockReset().mockResolvedValue(DATA)
  mockPost.mockReset()
})

describe('Health', () => {
  it('shows a real delta once a metric has a baseline', async () => {
    render(<Health />)
    await waitFor(() => expect(screen.getByText('68')).toBeInTheDocument())
    expect(screen.getByText('+8 vs 30d')).toBeInTheDocument()
  })

  it('honestly reports building baseline for metrics without enough history', async () => {
    render(<Health />)
    await waitFor(() =>
      expect(screen.getAllByText(/building baseline/).length).toBeGreaterThan(0),
    )
    expect(screen.getByText('building baseline, 5 of 30 nights')).toBeInTheDocument()
  })
})
