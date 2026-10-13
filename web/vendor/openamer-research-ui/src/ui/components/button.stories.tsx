import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect } from 'storybook/test'

import { Button } from './button'
import { ArrowIcon, LinkIcon, SearchIcon } from './icons'

const meta: Meta<typeof Button> = {
  argTypes: {
    children: { control: 'text' },
    disabled: { control: 'boolean' },
    invert: { control: 'boolean' },
    outlined: { control: 'boolean' }
  },
  args: { children: 'Normal', disabled: false, invert: false, outlined: false },
  component: Button,
  title: 'Components/Forms/Button'
}

export default meta

type Story = StoryObj<typeof Button>

export const Playground: Story = {
  args: { prefix: <ArrowIcon direction="right" /> }
}

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-2">
      <Button prefix={<ArrowIcon direction="right" />}>Normal</Button>
      <Button invert prefix={<ArrowIcon direction="right" />}>
        Inverted
      </Button>
      <Button outlined prefix={<ArrowIcon direction="right" />}>
        Outlined
      </Button>
      <Button invert outlined prefix={<ArrowIcon direction="right" />}>
        Out + Inv
      </Button>
    </div>
  )
}

export const WithIcons: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-2">
      <Button suffix={<LinkIcon />}>Suffix</Button>
      <Button
        prefix={<SearchIcon />}
        suffix={<ArrowIcon direction="right" />}
      >
        Prefix + Suffix
      </Button>
      <Button disabled prefix={<ArrowIcon direction="right" />}>
        Disabled
      </Button>
    </div>
  )
}

export const CssCheck: Story = {
  args: { children: 'Danger', destructive: true },
  play: async ({ canvas }) => {
    const button = canvas.getByRole('button', { name: /danger/i })

    await expect(getComputedStyle(button).backgroundColor).toBe('rgb(251, 44, 54)')
  }
}
