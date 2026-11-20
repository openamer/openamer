import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { BrandLoader } from './brand-loader'

describe('BrandLoader', () => {
  afterEach(cleanup)

  it('announces itself as a status with the given label', () => {
    render(<BrandLoader label="Checking for updates" />)

    expect(screen.getByRole('status', { name: 'Checking for updates' })).toBeTruthy()
  })

  it('draws the O/A monogram: one O track, one sweep, two A strokes', () => {
    const { container } = render(<BrandLoader />)
    const circles = container.querySelectorAll('circle')
    const paths = container.querySelectorAll('path')

    expect(circles).toHaveLength(2)
    expect(paths).toHaveLength(2)

    // Every stroke paints the same brand gradient, and the A strokes start
    // erased so the CSS keyframes write them in.
    const gradient = container.querySelector('linearGradient')

    expect(gradient).toBeTruthy()
    expect(gradient?.getAttribute('id')).toBeTruthy()

    for (const node of [...circles, ...paths]) {
      expect(node.getAttribute('stroke')).toBe(`url(#${gradient?.getAttribute('id')})`)
    }

    for (const path of paths) {
      expect(path.getAttribute('pathLength')).toBe('100')
      expect(path.getAttribute('stroke-dashoffset')).toBe('100')
    }

    expect(container.querySelectorAll('stop')).toHaveLength(2)
  })

  it('keeps gradient ids unique per instance so two loaders cannot cross-wire', () => {
    const { container } = render(
      <>
        <BrandLoader />
        <BrandLoader />
      </>
    )

    const ids = [...container.querySelectorAll('linearGradient')].map(node => node.getAttribute('id'))

    expect(ids).toHaveLength(2)
    expect(new Set(ids).size).toBe(2)
  })

  it('stays decorative when the parent already owns the live region', () => {
    render(<BrandLoader decorative />)

    expect(screen.queryByRole('status')).toBeNull()
  })
})
