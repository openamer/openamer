import type { Meta, StoryObj } from '@storybook/react-vite'

import { BarChart, LineChart } from '../graphs'
import { Small } from '../typography/small'

const LINE_DATA = (['primary', 'secondary', 'tertiary'] as const).flatMap(
  (series, si) =>
    [0, 50000, 100000, 150000].map((label, i) => ({
      label,
      series,
      value: 0.15 + si * 0.1 + (i % 2) * 0.05 + Math.sin(i + si) * 0.08
    }))
)

const BAR_DATA = (() => {
  let x = 42
  const f = () => (x = (1103515245 * x + 12345) % 0x80000000) / 0x80000000

  return Array.from({ length: 100 }, (_, i) => ({
    label: (i / 99) * 150000,
    value: f() * 10
  }))
})()

const meta = {
  parameters: { layout: 'padded' },
  title: 'Components/Data Display/Graphs'
} satisfies Meta

export default meta

type Story = StoryObj

export const Line: Story = {
  render: () => (
    <div>
      <Small className="mb-5 block opacity-50">LineChart</Small>

      <LineChart
        data={LINE_DATA}
        series="series"
        x="label"
        y="value"
        yDomain={[0, 0.5]}
      />
    </div>
  )
}

export const Bar: Story = {
  render: () => (
    <div>
      <Small className="mb-5 block opacity-50">BarChart</Small>

      <BarChart
        data={BAR_DATA}
        x="label"
        xDomain={[0, 150000]}
        y="value"
        yDomain={[0, 10]}
      />
    </div>
  )
}
