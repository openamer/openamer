import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import {
  AnimatedCount,
  useAnimatedCount
} from './animated-count'
import { Button } from './button'
import { Typography } from './typography'
import { Small } from './typography/small'

const meta = {
  args: { damping: 1, duration: 1600, value: 84210 },
  component: AnimatedCount,
  title: 'Components/Feedback/AnimatedCount'
} satisfies Meta<typeof AnimatedCount>

export default meta

type Story = StoryObj<typeof meta>

export const Playground: Story = {
  render: args => (
    <Typography className="text-4xl font-bold tabular-nums" expanded>
      <AnimatedCount {...args} />
    </Typography>
  )
}

function LiveCount() {
  const ts = useState(() => new Date())[0]
  const value = useAnimatedCount(1000, 12, ts)

  return <AnimatedCount duration={500} value={value} />
}

export const Live: StoryObj = {
  render: () => (
    <div className="flex flex-col gap-2">
      <Small className="opacity-40">Live ticker (rate = 12)</Small>

      <Typography className="text-4xl font-bold tabular-nums" expanded>
        <LiveCount />
      </Typography>
    </div>
  )
}

export const Manual: StoryObj = {
  render: () => {
    const [value, setValue] = useState(100)

    return (
      <div className="flex flex-col gap-4">
        <Typography className="text-4xl font-bold tabular-nums" expanded>
          <AnimatedCount duration={800} value={value} />
        </Typography>

        <div className="flex gap-2">
          <Button onClick={() => setValue(v => v + 1000)}>+1000</Button>
          <Button onClick={() => setValue(v => v + 100)}>+100</Button>
          <Button onClick={() => setValue(v => Math.max(0, v - 100))}>-100</Button>
        </div>
      </div>
    )
  }
}
