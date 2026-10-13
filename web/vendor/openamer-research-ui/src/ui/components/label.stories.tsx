import type { Meta, StoryObj } from '@storybook/react-vite'

import { Input } from './input'
import { Label } from './label'

const meta: Meta<typeof Label> = {
  component: Label,
  title: 'Components/Forms/Label'
}

export default meta

type Story = StoryObj<typeof Label>

export const Playground: Story = {
  render: () => <Label>Field label</Label>
}

export const WithInput: Story = {
  render: () => (
    <div className="grid w-64 gap-1.5">
      <Label htmlFor="label-demo">API key</Label>
      <Input id="label-demo" type="password" placeholder="sk-…" />
    </div>
  )
}
