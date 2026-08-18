import type { Meta, StoryObj } from '@storybook/react-vite'

import { Watchlist } from './watchlist'

const ADDRESSES = [
  ['0x7a16fF8270133F063aAb6C9977183D9e72835428', '0.50%'],
  ['0xd4e96eF8eEE8678dBFF4d535E015d1a77e7Cc62c', '1.20%'],
  ['0x2B5AD5c4795c026514f8317c7a215E218DcCD6cF', '3.00%'],
  ['0x8ba1f109551bD432803012645Ac136ddd64DBA72', '4.10%']
].map(([label, right]) => ({ label, right, url: '#' }))

const meta = {
  component: Watchlist,
  title: 'Components/Data Display/Watchlist'
} satisfies Meta<typeof Watchlist>

export default meta

type Story = StoryObj<typeof meta>

export const WithCounterAndScramble: Story = {
  args: { counter: true, items: ADDRESSES, scramble: true }
}

export const Simple: Story = {
  args: {
    items: [
      { label: 'One', right: '11%' },
      { label: 'Two', right: '22%' },
      { label: 'Three', right: '33%' }
    ]
  }
}
