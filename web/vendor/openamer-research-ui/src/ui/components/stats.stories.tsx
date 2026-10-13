import type { Meta, StoryObj } from '@storybook/react-vite'

import { Stats } from './stats'

const meta = {
  component: Stats,
  title: 'Components/Feedback/Stats'
} satisfies Meta<typeof Stats>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    items: [
      { label: 'Parameters', value: '36.2b' },
      { label: 'Checkpoint', value: 'Scratch' },
      { label: 'HfAuto', value: 'Auto' },
      { label: 'Type', value: 'Text' },
      { label: 'Loss', value: '0.56' }
    ]
  }
}
