import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { BrandMark } from './brand-mark'

describe('BrandMark', () => {
  it('renders the OpenAmer eye mark (openamer.png), not the atom placeholder', () => {
    const { container } = render(<BrandMark />)
    const img = container.querySelector('img')
    expect(img).toBeTruthy()
    expect(img?.getAttribute('src')).toMatch(/openamer\.png$/)
    expect(img?.getAttribute('src')).not.toMatch(/openamer-girl/)
  })

  it('renders inside the white tile wrapper with the passed className', () => {
    render(<BrandMark className="size-12" />)
    // alt="" marks the img presentational: role is "presentation", not "img"
    const img = screen.getByRole('presentation')
    expect(img).toBeTruthy()
    expect(img.parentElement?.className).toContain('bg-white')
    expect(img.parentElement?.className).toContain('size-12')
  })
})
