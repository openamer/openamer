import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

import { ListItem } from './list-item'

const PROVIDERS = [
  { count: 412, name: 'OpenAI', slug: 'openai' },
  { count: 38, name: 'Anthropic', slug: 'anthropic' },
  { count: 124, name: 'Google', slug: 'google' },
  { count: 7, name: 'Mistral', slug: 'mistral' },
  { count: 4, name: 'xAI', slug: 'xai' }
]

function Demo() {
  const [active, setActive] = useState<string>('anthropic')

  return (
    <div className="w-72 border border-midground/15 bg-background-base">
      {PROVIDERS.map(p => (
        <ListItem
          active={p.slug === active}
          key={p.slug}
          onClick={() => setActive(p.slug)}
        >
          <span className="flex-1 truncate">{p.name}</span>
          <span className="text-[0.65rem] tabular-nums text-midground/50">
            {p.count}
          </span>
        </ListItem>
      ))}
    </div>
  )
}

const meta: Meta<typeof ListItem> = {
  component: ListItem,
  title: 'Components/Data Display/ListItem'
}

export default meta

type Story = StoryObj<typeof ListItem>

export const Playground: Story = { render: () => <Demo /> }

export const WithSubtitle: Story = {
  render: () => {
    function MultiLineDemo() {
      const [active, setActive] = useState<string>('anthropic')

      return (
        <div className="w-80 border border-midground/15 bg-background-base">
          {PROVIDERS.map(p => (
            <ListItem
              active={p.slug === active}
              key={p.slug}
              onClick={() => setActive(p.slug)}
            >
              <div className="flex-1 min-w-0">
                <div className="truncate font-medium">{p.name}</div>
                <div className="truncate text-[0.65rem] text-midground/60">
                  {p.slug} · {p.count} models
                </div>
              </div>
            </ListItem>
          ))}
        </div>
      )
    }

    return <MultiLineDemo />
  }
}

export const Disabled: Story = {
  render: () => (
    <div className="w-72 border border-midground/15 bg-background-base">
      <ListItem>Enabled item</ListItem>
      <ListItem disabled>Disabled item</ListItem>
      <ListItem active>Active item</ListItem>
    </div>
  )
}
