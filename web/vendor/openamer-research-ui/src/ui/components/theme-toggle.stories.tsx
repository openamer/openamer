import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import { HamburgerIcon } from './icons'
import { ThemeToggle } from './theme-toggle'
import { Small } from './typography/small'

const meta: Meta<typeof ThemeToggle> = {
  component: ThemeToggle,
  title: 'Components/Layout/ThemeToggle'
}

export default meta

type Story = StoryObj<typeof ThemeToggle>

export const Default: Story = {
  render: () => (
    <div className="flex items-center gap-3">
      <Small className="opacity-50">Theme</Small>

      <ThemeToggle />
    </div>
  )
}

export const WithHamburger: Story = {
  name: 'Beside Hamburger',
  render: () => {
    const [open, setOpen] = useState(false)

    return (
      <div className="flex items-center gap-3">
        <ThemeToggle />

        <button
          aria-label={open ? 'Close menu' : 'Open menu'}
          className="cursor-pointer bg-transparent p-2"
          onClick={() => setOpen(v => !v)}
          type="button"
        >
          <HamburgerIcon open={open} />
        </button>
      </div>
    )
  }
}
