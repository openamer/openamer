import type { Meta, StoryObj } from '@storybook/react-vite'

import { HoverBg } from './hover-bg'
import { Typography } from './typography'

const meta = {
  component: HoverBg,
  title: 'Components/Layout/HoverBg'
} satisfies Meta<typeof HoverBg>

export default meta

type Story = StoryObj<typeof meta>

export const Row: Story = {
  render: () => (
    <div className="flex gap-2">
      {['Alpha', 'Beta', 'Gamma'].map(label => (
        <div
          className="group relative flex items-center justify-center px-6 py-3"
          key={label}
        >
          <Typography mono>{label}</Typography>
          <HoverBg />
        </div>
      ))}
    </div>
  )
}
