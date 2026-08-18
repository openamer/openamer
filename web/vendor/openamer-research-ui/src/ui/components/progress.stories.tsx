import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import { Button } from './button'
import { Progress } from './progress'

const meta: Meta<typeof Progress> = {
  args: { animate: true, speed: 0.4, value: 42 },
  component: Progress,
  title: 'Components/Feedback/Progress'
}

export default meta

type Story = StoryObj<typeof Progress>

export const Playground: Story = {
  args: { children: '42%' }
}

export const Stages: Story = {
  render: () => (
    <div className="flex flex-col gap-3">
      <Progress value={15} />
      <Progress value={42}>42%</Progress>
      <Progress value={75}>75%</Progress>
      <Progress value={100}>Complete</Progress>
    </div>
  )
}

export const Interactive: Story = {
  render: () => {
    const [value, setValue] = useState(42)

    return (
      <div className="flex flex-col gap-4">
        <Progress value={value}>{value}%</Progress>

        <div className="flex gap-2">
          <Button onClick={() => setValue(v => Math.max(0, v - 10))}>-10</Button>

          <Button onClick={() => setValue(v => Math.min(100, v + 10))}>+10</Button>
        </div>
      </div>
    )
  }
}
