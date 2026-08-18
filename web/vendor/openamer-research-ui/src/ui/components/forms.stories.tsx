import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import { Button } from './button'
import { Checkbox } from './checkbox'
import { Input } from './input'
import { Label } from './label'
import { Select, SelectOption } from './select'
import { Separator } from './separator'
import { Switch } from './switch'

const meta: Meta = {
  title: 'Components/Forms/All Forms'
}

export default meta

type Story = StoryObj

export const AllFormControls: Story = {
  render: () => {
    function FormDemo() {
      const [name, setName] = useState('OpenAmer')
      const [email, setEmail] = useState('openamer@openamerresearch.com')
      const [provider, setProvider] = useState('anthropic')
      const [logging, setLogging] = useState(true)
      const [telemetry, setTelemetry] = useState(false)
      const [terms, setTerms] = useState(false)
      const [newsletter, setNewsletter] = useState(true)

      return (
        <div className="flex w-full max-w-lg flex-col gap-6">
          <div className="flex flex-col gap-1">
            <h2 className="font-expanded text-sm font-bold tracking-[0.08em] uppercase">
              Form Controls
            </h2>

            <p className="font-mondwest text-xs text-midground/60">
              All form primitives from the design system.
            </p>
          </div>

          <Separator />

          <div className="flex flex-col gap-4">
            <Label className="text-midground/50">Text Inputs</Label>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="form-name">Name</Label>
              <Input
                id="form-name"
                onChange={e => setName(e.target.value)}
                placeholder="Enter your name"
                value={name}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="form-email">Email</Label>
              <Input
                id="form-email"
                onChange={e => setEmail(e.target.value)}
                placeholder="Enter your email"
                type="email"
                value={email}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="form-disabled">Disabled Input</Label>
              <Input
                disabled
                id="form-disabled"
                placeholder="Cannot edit"
                value="Read-only value"
              />
            </div>
          </div>

          <Separator />

          <div className="flex flex-col gap-4">
            <Label className="text-midground/50">Select</Label>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="form-provider">Provider</Label>

              <Select
                onValueChange={setProvider}
                placeholder="Choose a provider…"
                value={provider}
              >
                <SelectOption value="openai">OpenAI</SelectOption>
                <SelectOption value="anthropic">Anthropic</SelectOption>
                <SelectOption value="google">Google</SelectOption>
                <SelectOption value="mistral">Mistral</SelectOption>
              </Select>
            </div>
          </div>

          <Separator />

          <div className="flex flex-col gap-4">
            <Label className="text-midground/50">Switches</Label>

            <label className="flex items-center justify-between">
              <span className="text-sm">Enable logging</span>
              <Switch checked={logging} onCheckedChange={setLogging} />
            </label>

            <label className="flex items-center justify-between">
              <span className="text-sm">Send telemetry</span>
              <Switch checked={telemetry} onCheckedChange={setTelemetry} />
            </label>
          </div>

          <Separator />

          <div className="flex flex-col gap-4">
            <Label className="text-midground/50">Checkboxes</Label>

            <div className="flex items-center gap-2.5">
              <Checkbox
                checked={terms}
                id="form-terms"
                onCheckedChange={setTerms}
              />

              <label className="cursor-pointer text-sm" htmlFor="form-terms">
                Accept terms and conditions
              </label>
            </div>

            <div className="flex items-center gap-2.5">
              <Checkbox
                checked={newsletter}
                id="form-newsletter"
                onCheckedChange={setNewsletter}
              />

              <label className="cursor-pointer text-sm" htmlFor="form-newsletter">
                Subscribe to newsletter
              </label>
            </div>
          </div>

          <Separator />

          <div className="flex flex-col gap-4">
            <Label className="text-midground/50">Buttons</Label>

            <div className="flex flex-wrap gap-2">
              <Button>Primary</Button>
              <Button outlined>Outlined</Button>
              <Button invert>Inverted</Button>
              <Button destructive>Destructive</Button>
              <Button disabled>Disabled</Button>
            </div>
          </div>

          <Separator />

          <div className="flex items-center justify-end gap-2">
            <Button outlined>Cancel</Button>
            <Button>Save Changes</Button>
          </div>
        </div>
      )
    }

    return <FormDemo />
  }
}
