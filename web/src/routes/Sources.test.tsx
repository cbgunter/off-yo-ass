import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Sources } from './Sources'

describe('Sources', () => {
  it('lists every known source as not connected, honestly', () => {
    render(<Sources />)
    expect(screen.getByText('Garmin')).toBeInTheDocument()
    expect(screen.getAllByText('not connected').length).toBeGreaterThan(0)
  })
})
