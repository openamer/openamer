import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import { Button } from './button'
import { ConfirmDialog } from './confirm-dialog'

const meta: Meta<typeof ConfirmDialog> = {
  component: ConfirmDialog,
  title: 'Components/Overlays/ConfirmDialog'
}

export default meta

type Story = StoryObj<typeof ConfirmDialog>

export const Default: Story = {
  render: () => {
    function Demo() {
      const [open, setOpen] = useState(false)

      return (
        <>
          <Button onClick={() => setOpen(true)}>Open dialog</Button>

          <ConfirmDialog
            description="This action cannot be undone."
            onCancel={() => setOpen(false)}
            onConfirm={() => setOpen(false)}
            open={open}
            title="Are you sure?"
          />
        </>
      )
    }

    return <Demo />
  }
}

export const Destructive: Story = {
  render: () => {
    function Demo() {
      const [open, setOpen] = useState(false)

      return (
        <>
          <Button destructive onClick={() => setOpen(true)}>
            Delete item
          </Button>

          <ConfirmDialog
            confirmLabel="Delete"
            description="This will permanently delete the item. This action cannot be undone."
            destructive
            onCancel={() => setOpen(false)}
            onConfirm={() => setOpen(false)}
            open={open}
            title="Delete item?"
          />
        </>
      )
    }

    return <Demo />
  }
}

export const Loading: Story = {
  render: () => {
    function Demo() {
      const [open, setOpen] = useState(false)

      return (
        <>
          <Button onClick={() => setOpen(true)}>With loading state</Button>

          <ConfirmDialog
            description="Simulating a loading state."
            loading
            onCancel={() => setOpen(false)}
            onConfirm={() => {}}
            open={open}
            title="Processing…"
          />
        </>
      )
    }

    return <Demo />
  }
}
