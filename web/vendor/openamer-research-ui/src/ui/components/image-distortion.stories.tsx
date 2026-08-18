import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import fillerBg from '../../assets/filler-bg0.webp'
import { Button } from './button'
import { ImageDistortion } from './image-distortion'

const meta: Meta<typeof ImageDistortion> = {
  args: { active: true, src: fillerBg.src ?? (fillerBg as unknown as string) },
  component: ImageDistortion,
  title: 'Components/Effects/ImageDistortion'
}

export default meta

type Story = StoryObj<typeof ImageDistortion>

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="bg-background-base relative h-[420px] w-[560px] overflow-hidden border border-current/20"
      style={{ backgroundColor: 'var(--background)' }}
    >
      {children}
    </div>
  )
}

export const Default: Story = {
  render: args => (
    <Frame>
      <ImageDistortion {...args} />
    </Frame>
  )
}

export const Tinted: Story = {
  args: { tint: '#88ccaa' },
  render: args => (
    <Frame>
      <ImageDistortion {...args} />
    </Frame>
  )
}

export const TintStrength: Story = {
  render: () => {
    const src = fillerBg.src ?? (fillerBg as unknown as string)

    return (
      <div className="grid grid-cols-3 gap-4">
        {[
          ['#88ccaa', 'mint'],
          ['#ccaa88', 'amber'],
          ['#ff4444', 'fatal']
        ].map(([tint, label]) => (
          <div className="flex flex-col gap-2" key={label}>
            <span className="text-xs uppercase tracking-widest opacity-50">
              {label}
            </span>

            <Frame>
              <ImageDistortion
                src={src}
                tint={tint}
                tintStrength={{ active: 0.55, inactive: 0.25 }}
              />
            </Frame>
          </div>
        ))}
      </div>
    )
  }
}

/**
 * Runs the haptic-distortion effect on a choreographed motion pattern so
 * the image looks alive without needing a real pointer. Perfect for
 * screen recordings, posters, and social cuts.
 */
export const AutoPlay: Story = {
  render: () => {
    const src = fillerBg.src ?? (fillerBg as unknown as string)

    return (
      <div className="grid grid-cols-3 gap-4">
        {(['slash', 'gentle', 'aggressive'] as const).map(pattern => (
          <div className="flex flex-col gap-2" key={pattern}>
            <span className="text-xs uppercase tracking-widest opacity-50">
              {pattern}
            </span>

            <Frame>
              <ImageDistortion autoPlay={pattern} src={src} tint="#ccaa88" />
            </Frame>
          </div>
        ))}
      </div>
    )
  }
}

export const ToggleActive: Story = {
  render: () => {
    const [active, setActive] = useState(true)
    const src = fillerBg.src ?? (fillerBg as unknown as string)

    return (
      <div className="flex flex-col gap-3">
        <Frame>
          <ImageDistortion active={active} src={src} tint="#ff4444" />
        </Frame>

        <Button onClick={() => setActive(v => !v)}>
          {active ? 'Active' : 'Inactive'}
        </Button>
      </div>
    )
  }
}
