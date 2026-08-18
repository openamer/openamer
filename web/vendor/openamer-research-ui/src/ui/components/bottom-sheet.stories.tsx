import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import { BottomSheet } from './bottom-sheet'
import { Button } from './button'
import { ListItem } from './list-item'

const meta: Meta<typeof BottomSheet> = {
  component: BottomSheet,
  title: 'Components/Overlays/BottomSheet'
}

export default meta

type Story = StoryObj<typeof BottomSheet>

export const Default: Story = {
  render: () => {
    function Demo() {
      const [open, setOpen] = useState(false)

      return (
        <>
          <Button onClick={() => setOpen(true)}>Open sheet</Button>

          <BottomSheet
            onClose={() => setOpen(false)}
            open={open}
            title="Pick an option"
          >
            {['Alpha', 'Beta', 'Gamma', 'Delta'].map(item => (
              <ListItem key={item} onClick={() => setOpen(false)}>
                {item}
              </ListItem>
            ))}
          </BottomSheet>
        </>
      )
    }

    return <Demo />
  }
}
