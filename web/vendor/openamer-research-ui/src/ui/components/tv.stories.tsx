import type { Meta, StoryObj } from '@storybook/react-vite'
import { Suspense } from 'react'

import { TV } from './tv'

const meta = {
  component: TV,
  parameters: {
    docs: {
      description: {
        component:
          'Animated WebGL brush inside an SVG television frame. Renders a fragment shader, so it only makes sense on the client.'
      }
    }
  },
  title: 'Components/Effects/TV'
} satisfies Meta<typeof TV>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Suspense>
      <TV className="h-64 w-64" />
    </Suspense>
  )
}

export const Large: Story = {
  render: () => (
    <Suspense>
      <TV className="h-[28rem] w-[28rem]" />
    </Suspense>
  )
}
