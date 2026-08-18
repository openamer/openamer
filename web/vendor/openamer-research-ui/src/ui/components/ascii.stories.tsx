import type { Meta, StoryObj } from '@storybook/react-vite'

import { AsciiSkeleton, Scramble } from './ascii'
import { Typography } from './typography'

const meta = {
  title: 'Components/Effects/Ascii'
} satisfies Meta

export default meta

type Story = StoryObj

export const RevealScramble: Story = {
  render: () => (
    <Typography className="text-lg" mono>
      <Scramble delay={200} text="PSYCHE NETWORK" />
    </Typography>
  )
}

export const Skeleton: Story = {
  render: () => (
    <div className="flex flex-col gap-4">
      <AsciiSkeleton cols={20} rows={1} />
      <AsciiSkeleton cols={40} rows={3} />
      <AsciiSkeleton cols={60} rows={5} speed={120} />
    </div>
  )
}
