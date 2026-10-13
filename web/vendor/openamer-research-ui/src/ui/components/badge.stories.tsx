import type { Meta, StoryObj } from '@storybook/react-vite'

import { Badge } from './badge'
import { OpenAmerGirlBadge } from './badges/openamer-girl'

const meta = {
  args: { children: 'LIVE' },
  component: Badge,
  title: 'Components/Feedback/Badge'
} satisfies Meta<typeof Badge>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const Row: Story = {
  render: () => (
    <div className="flex items-center gap-3">
      <Badge>2.47</Badge>
      <Badge>LIVE</Badge>
      <Badge>14B</Badge>
      <Badge>DEMO</Badge>
    </div>
  )
}

export const OpenAmerGirl: StoryObj = {
  render: () => <OpenAmerGirlBadge className="h-20 w-auto" />
}
