import type { Meta, StoryObj } from '@storybook/react-vite'

import { Tabs, TabsList, TabsTrigger } from './tabs'
import { Small } from './typography/small'

const meta: Meta<typeof Tabs> = {
  component: Tabs,
  title: 'Components/Forms/Tabs'
}

export default meta

type Story = StoryObj<typeof Tabs>

export const Playground: Story = {
  render: () => (
    <div className="w-[28rem]">
      <Tabs defaultValue="overview">
        {(active, setActive) => (
          <>
            <TabsList>
              <TabsTrigger
                active={active === 'overview'}
                onClick={() => setActive('overview')}
                value="overview"
              >
                Overview
              </TabsTrigger>

              <TabsTrigger
                active={active === 'metrics'}
                onClick={() => setActive('metrics')}
                value="metrics"
              >
                Metrics
              </TabsTrigger>

              <TabsTrigger
                active={active === 'logs'}
                onClick={() => setActive('logs')}
                value="logs"
              >
                Logs
              </TabsTrigger>

              <TabsTrigger
                active={active === 'settings'}
                onClick={() => setActive('settings')}
                value="settings"
              >
                Settings
              </TabsTrigger>
            </TabsList>

            <div className="p-4 border border-midground/10 bg-background-base">
              <Small className="opacity-60">
                Active panel: <span className="opacity-100">{active}</span>
              </Small>
            </div>
          </>
        )}
      </Tabs>
    </div>
  )
}

export const TwoTabs: Story = {
  render: () => (
    <div className="w-80">
      <Tabs defaultValue="local">
        {(active, setActive) => (
          <>
            <TabsList>
              <TabsTrigger
                active={active === 'local'}
                onClick={() => setActive('local')}
                value="local"
              >
                Local
              </TabsTrigger>

              <TabsTrigger
                active={active === 'remote'}
                onClick={() => setActive('remote')}
                value="remote"
              >
                Remote
              </TabsTrigger>
            </TabsList>

            <div className="p-4 border border-midground/10 bg-background-base">
              <Small className="opacity-60">
                Active panel: <span className="opacity-100">{active}</span>
              </Small>
            </div>
          </>
        )}
      </Tabs>
    </div>
  )
}
