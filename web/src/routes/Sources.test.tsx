import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Sources } from './Sources'

vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn().mockResolvedValue([
      {
        name: 'Garmin',
        note: 'sleep, HRV, resting heart rate, weight',
        status: 'not_connected',
        last_synced: null,
      },
      {
        name: 'Google Calendar',
        note: 'tonight, tomorrow, travel',
        status: 'not_connected',
        last_synced: null,
      },
    ]),
  },
}))

describe('Sources', () => {
  it('lists sources from the API, honestly reporting not connected', async () => {
    render(<Sources />)
    await waitFor(() => expect(screen.getByText('Garmin')).toBeInTheDocument())
    expect(screen.getAllByText('not connected').length).toBeGreaterThan(0)
  })
})
