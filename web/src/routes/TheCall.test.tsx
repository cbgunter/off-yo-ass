import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TheCall } from './TheCall'

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: { get: mockGet, post: mockPost },
}))

const CALL = {
  headline: 'Resting heart rate is 8 bpm over your 30-day average.',
  prescription: { activity: 'walk', duration_min: 30, intensity: 'easy', window: '17:30-18:30' },
  why: 'Sleep was short.',
  fallback: 'A short walk works too.',
  skip_ok: false,
  overridden: false,
}

describe('TheCall', () => {
  it('walks through did_it -> feel -> done', async () => {
    mockGet.mockResolvedValue(CALL)
    mockPost.mockResolvedValue(undefined)
    const user = userEvent.setup()

    render(<TheCall />)

    await waitFor(() => expect(screen.getByText(CALL.headline)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Did it' }))
    expect(mockPost).toHaveBeenCalledWith('/call/checkin', { result: 'did_it' })

    await waitFor(() => expect(screen.getByText('How did it feel?')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Easy' }))
    expect(mockPost).toHaveBeenCalledWith('/call/feel', { feel: 'easy' })

    await waitFor(() => expect(screen.getByText('Logged.')).toBeInTheDocument())
  })

  it('walks through no -> skip reason -> done, with no feel tap', async () => {
    mockGet.mockResolvedValue(CALL)
    mockPost.mockResolvedValue(undefined)
    const user = userEvent.setup()

    render(<TheCall />)

    await waitFor(() => expect(screen.getByText(CALL.headline)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'No' }))
    await waitFor(() => expect(screen.getByText('Why not?')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Too tired' }))
    expect(mockPost).toHaveBeenCalledWith('/call/checkin', {
      result: 'no',
      skip_reason: 'too_tired',
    })

    await waitFor(() => expect(screen.getByText('Logged.')).toBeInTheDocument())
    expect(screen.queryByText('How did it feel?')).not.toBeInTheDocument()
  })

  it('shows an empty state when no call has been generated yet', async () => {
    mockGet.mockResolvedValue(null)
    render(<TheCall />)
    await waitFor(() =>
      expect(screen.getByText('No call yet. Check back at 15:45.')).toBeInTheDocument(),
    )
  })
})
