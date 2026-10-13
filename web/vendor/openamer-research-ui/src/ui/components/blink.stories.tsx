import type { Meta, StoryObj } from '@storybook/react-vite'

import { Blink } from './blink'
import { Typography } from './typography'
import { Small } from './typography/small'

const meta = {
  component: Blink,
  title: 'Components/Effects/Blink'
} satisfies Meta<typeof Blink>

export default meta

type Story = StoryObj<typeof meta>

export const Cursors: Story = {
  render: () => (
    <div className="group flex flex-col gap-3">
      <Small className="opacity-40">Hover to see the cursors blink</Small>

      <Typography className="relative" mono>
        Block
        <Blink className="absolute" cursor="block" />
      </Typography>

      <Typography className="relative" mono>
        Line
        <Blink className="absolute" cursor="line" />
      </Typography>
    </div>
  )
}
