import type { Meta, StoryObj } from '@storybook/react-vite'

import { FitText } from '../fit-text'

const meta: Meta<typeof FitText> = {
  args: { children: 'Fit Text', max: 'infinity * 1px', min: '1em' },
  component: FitText,
  title: 'Components/Effects/FitText'
}

export default meta

type Story = StoryObj<typeof FitText>

export const Playground: Story = {}

export const Fills: Story = {
  render: () => (
    <div className="w-full">
      <FitText className="font-sans font-bold">Design System</FitText>
    </div>
  )
}

export const CappedMax: Story = {
  render: () => (
    <div className="w-full">
      <FitText className="font-mondwest" max="4rem">
        Capped max at 4rem
      </FitText>
    </div>
  )
}
