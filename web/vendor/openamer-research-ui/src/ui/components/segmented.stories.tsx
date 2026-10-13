import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import {
  FilterGroup,
  Segmented
} from './segmented'

type Density = 'compact' | 'comfortable' | 'spacious'
type Severity = 'all' | 'info' | 'warn' | 'error'

const DENSITY_OPTIONS: { label: string; value: Density }[] = [
  { label: 'Compact', value: 'compact' },
  { label: 'Comfortable', value: 'comfortable' },
  { label: 'Spacious', value: 'spacious' }
]

const SEVERITY_OPTIONS: { label: string; value: Severity }[] = [
  { label: 'All', value: 'all' },
  { label: 'Info', value: 'info' },
  { label: 'Warn', value: 'warn' },
  { label: 'Error', value: 'error' }
]

function Demo({ size }: { size?: 'md' | 'sm' }) {
  const [value, setValue] = useState<Density>('comfortable')

  return (
    <Segmented
      onChange={setValue}
      options={DENSITY_OPTIONS}
      size={size}
      value={value}
    />
  )
}

const meta: Meta<typeof Segmented> = {
  component: Segmented,
  title: 'Components/Forms/Segmented'
}

export default meta

type Story = StoryObj<typeof Segmented>

export const Playground: Story = { render: () => <Demo /> }

export const Medium: Story = { render: () => <Demo size="md" /> }

export const TwoOptions: Story = {
  render: () => {
    function TwoOptionsDemo() {
      const [value, setValue] = useState<'on' | 'off'>('on')

      return (
        <Segmented
          onChange={setValue}
          options={[
            { label: 'On', value: 'on' },
            { label: 'Off', value: 'off' }
          ]}
          value={value}
        />
      )
    }

    return <TwoOptionsDemo />
  }
}

export const InFilterGroup: Story = {
  render: () => {
    function FilterDemo() {
      const [severity, setSeverity] = useState<Severity>('all')
      const [density, setDensity] = useState<Density>('comfortable')

      return (
        <div className="flex flex-wrap items-center gap-6">
          <FilterGroup label="Severity">
            <Segmented
              onChange={setSeverity}
              options={SEVERITY_OPTIONS}
              value={severity}
            />
          </FilterGroup>

          <FilterGroup label="Density">
            <Segmented
              onChange={setDensity}
              options={DENSITY_OPTIONS}
              value={density}
            />
          </FilterGroup>
        </div>
      )
    }

    return <FilterDemo />
  }
}
