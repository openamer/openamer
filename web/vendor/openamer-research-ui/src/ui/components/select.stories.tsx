import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import { Select, SelectOption } from './select'
import { Small } from './typography/small'

const PROVIDERS = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Google', value: 'google' },
  { label: 'Mistral', value: 'mistral' },
  { label: 'xAI', value: 'xai' }
]

function Demo({
  disabled,
  placeholder
}: {
  disabled?: boolean
  placeholder?: string
}) {
  const [value, setValue] = useState<string>('anthropic')

  return (
    <div className="w-72">
      <Select
        disabled={disabled}
        onValueChange={setValue}
        placeholder={placeholder}
        value={value}
      >
        {PROVIDERS.map(p => (
          <SelectOption key={p.value} value={p.value}>
            {p.label}
          </SelectOption>
        ))}
      </Select>
    </div>
  )
}

const meta: Meta<typeof Select> = {
  component: Select,
  title: 'Components/Forms/Select'
}

export default meta

type Story = StoryObj<typeof Select>

export const Playground: Story = { render: () => <Demo /> }

export const Disabled: Story = { render: () => <Demo disabled /> }

export const Empty: Story = {
  render: () => {
    function EmptyDemo() {
      const [value, setValue] = useState<string>('')

      return (
        <div className="w-72">
          <Select
            onValueChange={setValue}
            placeholder="Choose a provider…"
            value={value}
          >
            {PROVIDERS.map(p => (
              <SelectOption key={p.value} value={p.value}>
                {p.label}
              </SelectOption>
            ))}
          </Select>
        </div>
      )
    }

    return <EmptyDemo />
  }
}

export const NextToLabel: Story = {
  render: () => (
    <div className="grid w-72 gap-2">
      <Small className="opacity-60 uppercase tracking-wider">Provider</Small>
      <Demo />
    </div>
  )
}
