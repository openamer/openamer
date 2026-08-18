import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import { Checkbox } from './checkbox'
import { Small } from './typography/small'

function Demo({ disabled }: { disabled?: boolean }) {
  const [checked, setChecked] = useState(false)

  return (
    <div className="flex items-center gap-2.5">
      <Checkbox
        checked={checked}
        disabled={disabled}
        id="checkbox-demo"
        onCheckedChange={setChecked}
      />

      <label className="cursor-pointer text-sm" htmlFor="checkbox-demo">
        Accept terms
      </label>
    </div>
  )
}

const meta: Meta<typeof Checkbox> = {
  component: Checkbox,
  title: 'Components/Forms/Checkbox'
}

export default meta

type Story = StoryObj<typeof Checkbox>

export const Playground: Story = { render: () => <Demo /> }

export const Disabled: Story = { render: () => <Demo disabled /> }

export const Checked: Story = {
  render: () => (
    <div className="flex items-center gap-2.5">
      <Checkbox defaultChecked id="checkbox-checked" />

      <label className="cursor-pointer text-sm" htmlFor="checkbox-checked">
        Clone from default profile
      </label>
    </div>
  )
}

export const Stack: Story = {
  render: () => {
    function StackDemo() {
      const [a, setA] = useState(true)
      const [b, setB] = useState(false)
      const [c, setC] = useState(true)

      return (
        <div className="grid w-72 gap-3">
          <div className="flex items-center gap-2.5">
            <Checkbox checked={a} id="opt-a" onCheckedChange={setA} />

            <label className="cursor-pointer text-sm" htmlFor="opt-a">
              Logging
            </label>
          </div>

          <div className="flex items-center gap-2.5">
            <Checkbox checked={b} id="opt-b" onCheckedChange={setB} />

            <label className="cursor-pointer text-sm" htmlFor="opt-b">
              Telemetry
            </label>
          </div>

          <div className="flex items-center gap-2.5">
            <Checkbox checked={c} id="opt-c" onCheckedChange={setC} />

            <label className="cursor-pointer text-sm" htmlFor="opt-c">
              Auto-update
            </label>
          </div>
        </div>
      )
    }

    return <StackDemo />
  }
}

export const NextToLabel: Story = {
  render: () => {
    function LabeledDemo() {
      const [checked, setChecked] = useState(true)

      return (
        <div className="flex items-center gap-3">
          <Small className="opacity-60 uppercase tracking-wider">
            Persist globally
          </Small>

          <Checkbox
            checked={checked}
            id="persist-global"
            onCheckedChange={setChecked}
          />
        </div>
      )
    }

    return <LabeledDemo />
  }
}
