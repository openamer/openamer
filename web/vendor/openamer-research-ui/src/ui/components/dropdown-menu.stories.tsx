import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import { DropdownMenu } from './dropdown-menu'
import { Small } from './typography/small'

const OPTIONS = [
  { label: 'Option A', value: 'a' as const },
  { label: 'Option B', value: 'b' as const },
  { label: 'Option C', value: 'c' as const }
]

function Demo({ direction }: { direction: 'down' | 'left' | 'right' | 'up' }) {
  const [value, setValue] = useState<'a' | 'b' | 'c'>('a')

  return (
    <DropdownMenu
      direction={direction}
      onChange={setValue}
      options={OPTIONS}
      value={value}
    />
  )
}

const meta: Meta<typeof DropdownMenu> = {
  component: DropdownMenu,
  title: 'Components/Overlays/DropdownMenu'
}

export default meta

type Story = StoryObj<typeof DropdownMenu>

export const Down: Story = { render: () => <Demo direction="down" /> }
export const Up: Story = { render: () => <Demo direction="up" /> }
export const Right: Story = { render: () => <Demo direction="right" /> }
export const Left: Story = { render: () => <Demo direction="left" /> }

export const AllDirections: Story = {
  render: () => (
    <div className="flex gap-10">
      {(['down', 'up', 'right', 'left'] as const).map(direction => (
        <div className="flex flex-col gap-1" key={direction}>
          <Small className="capitalize opacity-40">{direction}</Small>

          <Demo direction={direction} />
        </div>
      ))}
    </div>
  )
}
