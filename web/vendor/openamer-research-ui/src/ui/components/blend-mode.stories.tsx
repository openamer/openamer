import type { Meta, StoryObj } from '@storybook/react-vite'

import { BlendMode } from './blend-mode'

const meta: Meta<typeof BlendMode> = {
  component: BlendMode,
  title: 'Components/Effects/BlendMode'
}

export default meta

type Story = StoryObj<typeof BlendMode>

export const Static: Story = {
  args: {
    background: 'mg/0.1',
    children: 'BlendMode static',
    className: 'p-3',
    color: 'fg'
  }
}

export const RenderProp: Story = {
  render: () => (
    <BlendMode background="mg/0.05" color="mg">
      {colors => (
        <div className="p-3" style={colors}>
          Render-prop variant (receives `{'{ backgroundColor, color }'}`)
        </div>
      )}
    </BlendMode>
  )
}
