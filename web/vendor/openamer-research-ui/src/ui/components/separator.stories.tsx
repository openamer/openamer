import type { Meta, StoryObj } from '@storybook/react-vite'

import { Separator } from './separator'
import { Small } from './typography/small'

const meta: Meta<typeof Separator> = {
  component: Separator,
  title: 'Components/Layout/Separator'
}

export default meta

type Story = StoryObj<typeof Separator>

export const Horizontal: Story = {
  render: () => (
    <div className="grid w-64 gap-3">
      <Small className="opacity-60 uppercase tracking-wider">Section A</Small>
      <Separator />
      <Small className="opacity-60 uppercase tracking-wider">Section B</Small>
    </div>
  )
}

export const Vertical: Story = {
  render: () => (
    <div className="flex h-8 items-center gap-3">
      <Small className="opacity-60 uppercase tracking-wider">Left</Small>
      <Separator orientation="vertical" />
      <Small className="opacity-60 uppercase tracking-wider">Right</Small>
    </div>
  )
}
