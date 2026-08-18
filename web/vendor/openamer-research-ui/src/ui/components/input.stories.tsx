import type { Meta, StoryObj } from '@storybook/react-vite'

import { Input } from './input'
import { Label } from './label'

const meta: Meta<typeof Input> = {
  component: Input,
  title: 'Components/Forms/Input'
}

export default meta

type Story = StoryObj<typeof Input>

export const Playground: Story = {
  render: () => <Input placeholder="Enter a value…" />
}

export const Disabled: Story = {
  render: () => <Input disabled placeholder="Disabled" value="locked" />
}

export const WithLabel: Story = {
  render: () => (
    <div className="grid w-64 gap-1.5">
      <Label htmlFor="demo-input">Model name</Label>
      <Input id="demo-input" placeholder="e.g. gpt-4o" />
    </div>
  )
}

export const NumberInput: Story = {
  render: () => (
    <div className="grid w-40 gap-1.5">
      <Label htmlFor="demo-number">Temperature</Label>
      <Input id="demo-number" type="number" step={0.1} defaultValue={0.7} />
    </div>
  )
}
