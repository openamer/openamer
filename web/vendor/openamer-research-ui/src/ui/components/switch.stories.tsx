import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import { Switch } from './switch'
import { Small } from './typography/small'

function Demo({ disabled }: { disabled?: boolean }) {
  const [checked, setChecked] = useState(false)

  return (
    <Switch checked={checked} disabled={disabled} onCheckedChange={setChecked} />
  )
}

const meta: Meta<typeof Switch> = {
  component: Switch,
  title: 'Components/Forms/Switch'
}

export default meta

type Story = StoryObj<typeof Switch>

export const Playground: Story = { render: () => <Demo /> }

export const Disabled: Story = { render: () => <Demo disabled /> }

export const NextToLabel: Story = {
  render: () => {
    function LabeledDemo() {
      const [checked, setChecked] = useState(true)

      return (
        <label className="flex items-center gap-3">
          <Small className="opacity-60 uppercase tracking-wider">
            Enable feature
          </Small>

          <Switch checked={checked} onCheckedChange={setChecked} />
        </label>
      )
    }

    return <LabeledDemo />
  }
}

export const Stack: Story = {
  render: () => {
    function StackDemo() {
      const [a, setA] = useState(true)
      const [b, setB] = useState(false)
      const [c, setC] = useState(true)

      return (
        <div className="grid w-64 gap-3">
          <label className="flex items-center justify-between">
            <Small className="opacity-60 uppercase tracking-wider">Logging</Small>
            <Switch checked={a} onCheckedChange={setA} />
          </label>

          <label className="flex items-center justify-between">
            <Small className="opacity-60 uppercase tracking-wider">Telemetry</Small>
            <Switch checked={b} onCheckedChange={setB} />
          </label>

          <label className="flex items-center justify-between">
            <Small className="opacity-60 uppercase tracking-wider">Auto-update</Small>
            <Switch checked={c} onCheckedChange={setC} />
          </label>
        </div>
      )
    }

    return <StackDemo />
  }
}
