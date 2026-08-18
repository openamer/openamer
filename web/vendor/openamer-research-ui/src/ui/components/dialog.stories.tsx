import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import { Button } from './button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from './dialog'
import { Input } from './input'
import { Label } from './label'

const meta: Meta<typeof Dialog> = {
  component: Dialog,
  title: 'Components/Overlays/Dialog'
}

export default meta

type Story = StoryObj<typeof Dialog>

export const Default: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild>
        <Button>Open Dialog</Button>
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Dialog Title</DialogTitle>
          <DialogDescription>
            A description of the dialog content and its purpose.
          </DialogDescription>
        </DialogHeader>

        <div className="p-4">
          <p className="font-courier text-sm text-midground/80">
            This is a general-purpose dialog built on Radix UI primitives. It
            handles focus trapping, ESC to close, and backdrop click
            automatically.
          </p>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button outlined>Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export const Controlled: Story = {
  render: () => {
    function Demo() {
      const [open, setOpen] = useState(false)

      return (
        <>
          <Button onClick={() => setOpen(true)}>Controlled Open</Button>

          <Dialog onOpenChange={setOpen} open={open}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Controlled Dialog</DialogTitle>
                <DialogDescription>
                  This dialog is controlled via external state.
                </DialogDescription>
              </DialogHeader>

              <div className="p-4">
                <p className="font-courier text-sm text-midground/80">
                  Open state is managed by the parent component. Useful when
                  you need to open the dialog programmatically.
                </p>
              </div>

              <DialogFooter>
                <Button onClick={() => setOpen(false)} outlined>
                  Cancel
                </Button>

                <Button onClick={() => setOpen(false)}>
                  Save
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </>
      )
    }

    return <Demo />
  }
}

export const WithForm: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild>
        <Button>Edit Profile</Button>
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Profile</DialogTitle>
          <DialogDescription>
            Make changes to your profile. Click save when you are done.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 p-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="name">Name</Label>
            <Input defaultValue="OpenAmer" id="name" />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input defaultValue="openamer@openamerresearch.com" id="email" type="email" />
          </div>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button outlined>Cancel</Button>
          </DialogClose>

          <DialogClose asChild>
            <Button>Save Changes</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export const NoCloseButton: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild>
        <Button>Without Close Button</Button>
      </DialogTrigger>

      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Minimal Dialog</DialogTitle>
          <DialogDescription>
            This dialog hides the X close button. Users can still close it
            by pressing ESC or clicking the backdrop.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <DialogClose asChild>
            <Button>Got it</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
