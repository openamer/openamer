import type { Meta, StoryObj } from '@storybook/react-vite'

import { Spinner } from './spinner'
import { Small } from './typography/small'

const NAMES = [
  'braille',
  'braillewave',
  'dna',
  'scan',
  'rain',
  'scanline',
  'pulse',
  'snake',
  'sparkle',
  'cascade',
  'columns',
  'orbit',
  'breathe',
  'waverows',
  'checkerboard',
  'helix',
  'fillsweep',
  'diagswipe'
] as const

const meta: Meta<typeof Spinner> = {
  component: Spinner,
  title: 'Components/Feedback/Spinner'
}

export default meta

type Story = StoryObj<typeof Spinner>

export const Playground: Story = { render: () => <Spinner /> }

export const InlineWithText: Story = {
  render: () => (
    <div className="flex items-center gap-2 text-sm text-midground/70">
      <Spinner /> Loading model info…
    </div>
  )
}

export const Sizes: Story = {
  render: () => (
    <div className="flex items-end gap-6">
      <div className="flex flex-col items-center gap-2">
        <Spinner className="text-xs" />
        <Small className="opacity-50">xs</Small>
      </div>

      <div className="flex flex-col items-center gap-2">
        <Spinner className="text-sm" />
        <Small className="opacity-50">sm</Small>
      </div>

      <div className="flex flex-col items-center gap-2">
        <Spinner className="text-base" />
        <Small className="opacity-50">base</Small>
      </div>

      <div className="flex flex-col items-center gap-2">
        <Spinner className="text-2xl" />
        <Small className="opacity-50">2xl</Small>
      </div>

      <div className="flex flex-col items-center gap-2">
        <Spinner className="text-4xl" />
        <Small className="opacity-50">4xl</Small>
      </div>
    </div>
  )
}

export const Tones: Story = {
  render: () => (
    <div className="flex items-center gap-4 text-base">
      <Spinner />
      <Spinner className="text-warning" />
      <Spinner className="text-success" />
      <Spinner className="text-destructive" />
      <Spinner className="text-midground/40" />
    </div>
  )
}

export const Gallery: Story = {
  render: () => (
    <div className="grid grid-cols-3 gap-x-8 gap-y-3 text-base">
      {NAMES.map(name => (
        <div className="flex items-center gap-3" key={name}>
          <Spinner name={name} />

          <Small className="font-mono opacity-60">{name}</Small>
        </div>
      ))}
    </div>
  )
}
