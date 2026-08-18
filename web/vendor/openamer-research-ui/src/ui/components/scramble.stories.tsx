import type { Meta, StoryObj } from '@storybook/react-vite'
import { useRef } from 'react'

import { Scramble } from './scramble'
import { Typography } from './typography'
import { Small } from './typography/small'

const meta: Meta<typeof Scramble> = {
  component: Scramble,
  title: 'Components/Effects/Scramble'
}

export default meta

type Story = StoryObj<typeof Scramble>

export const HoverToScramble: Story = {
  render: () => {
    const ref = useRef<HTMLDivElement>(null)

    return (
      <div className="flex flex-col gap-2" ref={ref}>
        <Small className="opacity-40">Hover the container</Small>

        <Typography as="div" className="text-lg" mono>
          <Scramble target={ref}>HOVER TO SCRAMBLE THIS TEXT</Scramble>
        </Typography>
      </div>
    )
  }
}

export const Tuned: Story = {
  render: () => {
    const ref = useRef<HTMLDivElement>(null)

    return (
      <div className="flex flex-col gap-2" ref={ref}>
        <Small className="opacity-40">dur=1200, spread=2</Small>

        <Typography as="div" className="text-lg" mono>
          <Scramble dur={1200} spread={2} target={ref}>
            FASTER WAVE, TIGHTER SPREAD
          </Scramble>
        </Typography>
      </div>
    )
  }
}
