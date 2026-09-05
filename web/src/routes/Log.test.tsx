import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Log } from './Log'

const { mockPost } = vi.hoisted(() => ({ mockPost: vi.fn() }))

vi.mock('@/lib/api', () => ({
  api: { post: mockPost },
}))

beforeEach(() => {
  mockPost.mockReset()
})

const ANALYSIS = {
  items: [{ name: 'Grilled chicken', portion: 'about 6 oz', calories: 280 }],
  total_calories: 650,
  protein_g: 45,
  carbs_g: 60,
  fat_g: 18,
  confidence: 'medium',
  notes: 'Assumed grilled, not fried.',
}

function mockAnalyzeThenSave() {
  mockPost.mockImplementation((path: string) => {
    if (path === '/meals/analyze') {
      return Promise.resolve({ photo_id: null, analysis: ANALYSIS })
    }
    return Promise.resolve(undefined)
  })
}

describe('Log a meal', () => {
  it('analyzes a description-only meal, then saves it', async () => {
    mockAnalyzeThenSave()
    const user = userEvent.setup()
    render(<Log />)

    await user.click(screen.getByRole('button', { name: 'Log a meal' }))
    await user.type(screen.getByLabelText('Description'), 'Chicken and rice')
    await user.click(screen.getByRole('button', { name: 'Analyze' }))

    await waitFor(() => expect(screen.getByText('650')).toBeInTheDocument())
    expect(mockPost).toHaveBeenCalledWith('/meals/analyze', {
      photo_base64: null,
      description: 'Chicken and rice',
    })
    expect(screen.getByText('Grilled chicken, about 6 oz')).toBeInTheDocument()
    expect(screen.getByText('Confidence: medium.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith('/meals', {
        photo_id: null,
        description: 'Chicken and rice',
        analysis: ANALYSIS,
      }),
    )

    await waitFor(() => expect(screen.getByText('Meal logged.')).toBeInTheDocument())
  })

  it('requires a photo or a description before analyzing', async () => {
    const user = userEvent.setup()
    render(<Log />)

    await user.click(screen.getByRole('button', { name: 'Log a meal' }))
    await user.click(screen.getByRole('button', { name: 'Analyze' }))

    expect(screen.getByText('Add a photo or a description.')).toBeInTheDocument()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('lets you go back and add detail before saving, instead of typing macros by hand', async () => {
    mockAnalyzeThenSave()
    const user = userEvent.setup()
    render(<Log />)

    await user.click(screen.getByRole('button', { name: 'Log a meal' }))
    await user.type(screen.getByLabelText('Description'), 'Chicken and rice')
    await user.click(screen.getByRole('button', { name: 'Analyze' }))
    await waitFor(() => expect(screen.getByText('650')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Add detail' }))

    expect(screen.getByLabelText('Description')).toHaveValue('Chicken and rice')
    expect(screen.queryByText('650')).not.toBeInTheDocument()
  })
})
