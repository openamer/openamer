import type { Meta, StoryObj } from '@storybook/react-vite'

import {
  TerminalDemo,
  type TerminalDemoStep
} from './terminal-demo'

const SEQUENCE: TerminalDemoStep[] = [
  { text: '❯ ', type: 'prompt' },
  {
    delay: 30,
    text: 'Research the latest approaches to GRPO training and write a summary',
    type: 'type'
  },
  { ms: 600, type: 'pause' },
  {
    lines: [
      '',
      '<span class="opacity-50">  web_search "GRPO reinforcement learning"         1.2s</span>',
      '<span class="opacity-50">  web_extract arxiv.org/abs/2402.03300             3.1s</span>',
      '<span class="opacity-50">  write_file ~/research/grpo-summary.md            0.1s</span>'
    ],
    type: 'output'
  },
  { ms: 500, type: 'pause' },
  {
    lines: [
      '',
      '<span class="opacity-70">Done! I\'ve written a summary covering:</span>',
      '',
      '<span class="opacity-70">  <span class="text-midground">✓</span> GRPO\'s group-relative advantage</span>',
      '<span class="opacity-70">  <span class="text-midground">✓</span> Comparison with PPO/DPO</span>',
      '',
      '<span class="opacity-70">Saved to</span> <span class="text-midground">~/research/grpo-summary.md</span>'
    ],
    type: 'output'
  },
  { ms: 2500, type: 'pause' },
  { type: 'clear' }
]

const meta: Meta<typeof TerminalDemo> = {
  args: { label: 'OpenAmer', sequence: SEQUENCE },
  component: TerminalDemo,
  title: 'Components/Data Display/TerminalDemo'
}

export default meta

type Story = StoryObj<typeof TerminalDemo>

export const Default: Story = {
  render: args => (
    <div className="w-[640px]">
      <TerminalDemo {...args} />
    </div>
  )
}

export const TallerWindow: Story = {
  args: { height: 480, label: 'shell' },
  render: args => (
    <div className="w-[640px]">
      <TerminalDemo {...args} />
    </div>
  )
}
