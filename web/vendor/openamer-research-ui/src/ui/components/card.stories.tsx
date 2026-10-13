import type { Meta, StoryObj } from '@storybook/react-vite'

import { Button } from './button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from './card'
import { Input } from './input'
import { Label } from './label'
import { Separator } from './separator'

const meta: Meta<typeof Card> = {
  component: Card,
  title: 'Components/Data Display/Card'
}

export default meta

type Story = StoryObj<typeof Card>

export const Default: Story = {
  render: () => (
    <Card className="max-w-sm">
      <CardHeader>
        <CardTitle>Card title</CardTitle>
        <CardDescription>A brief description of this card.</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-midground/70">
          Card body content goes here.
        </p>
      </CardContent>
    </Card>
  )
}

export const WithForm: Story = {
  render: () => (
    <Card className="max-w-sm">
      <CardHeader>
        <CardTitle>Settings</CardTitle>
        <CardDescription>Configure your preferences.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="card-name">Name</Label>
            <Input id="card-name" placeholder="Enter name…" />
          </div>

          <Separator />

          <div className="flex justify-end">
            <Button>Save</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
