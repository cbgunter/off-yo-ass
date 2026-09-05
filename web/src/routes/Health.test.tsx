import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
    blood_pressure: null,
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

  it('shows a no-data state for blood pressure, pointing at logging on this same screen', async () => {
    render(<Health />)
    await waitFor(() =>
      expect(screen.getByText('No readings yet. Log one below.')).toBeInTheDocument(),
    )
  })

  it('logs an activity via the relocated quick-log buttons', async () => {
    mockPost.mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(<Health />)
    await waitFor(() => expect(screen.getByText('68')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Split wood' }))
    // NoteBox (further down the same screen) has its own "Save" button --
    // the quick-log form's is the first of the two in DOM order.
    await user.click(screen.getAllByRole('button', { name: 'Save' })[0])

    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith('/quicklog/activity', {
        activity_type: 'wood_splitting',
        duration_min: 30,
      }),
    )
    await waitFor(() => expect(screen.getByText('Split wood logged.')).toBeInTheDocument())
  })

  it('logs blood pressure via the relocated quick-log button', async () => {
    mockPost.mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(<Health />)
    await waitFor(() => expect(screen.getByText('68')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Blood pressure' }))
    await user.type(screen.getByLabelText('Systolic'), '120')
    await user.type(screen.getByLabelText('Diastolic'), '80')
    await user.click(screen.getAllByRole('button', { name: 'Save' })[0])

    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith('/quicklog/bp', { systolic: 120, diastolic: 80 }),
    )
    await waitFor(() => expect(screen.getByText('Blood pressure logged.')).toBeInTheDocument())
  })
})
