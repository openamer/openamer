import type { Meta, StoryObj } from '@storybook/react-vite'

import {
  CommandBlock,
  CopyButton
} from './command-block'

const meta: Meta<typeof CommandBlock> = {
  args: {
    code: 'curl -fsSL https://openamer.openamerresearch.com/install.sh | bash',
    label: '1. Install'
  },
  component: CommandBlock,
  title: 'Components/Data Display/CommandBlock'
}

export default meta

type Story = StoryObj<typeof CommandBlock>

export const Default: Story = {
  render: args => (
    <div className="w-[520px]">
      <CommandBlock {...args} />
    </div>
  )
}

export const TwoStep: Story = {
  render: () => (
    <div className="flex w-[520px] flex-col gap-3">
      <CommandBlock
        code="curl -fsSL https://openamer.openamerresearch.com/install.sh | bash"
        label="1. Install"
      />

      <CommandBlock code="openamer setup" label="2. Configure" />
    </div>
  )
}

export const StandaloneButton: Story = {
  render: () => (
    <div className="flex items-center gap-3">
      <span className="font-courier text-xs opacity-60">
        echo &quot;hello world&quot;
      </span>

      <CopyButton text="echo 'hello world'" />
    </div>
  )
}
