import type { Meta, StoryObj } from '@storybook/react-vite'

import fillerBg from '../../assets/filler-bg0.webp'
import { TierCard } from './tier-card'

const SCOUT_SRC = fillerBg.src ?? (fillerBg as unknown as string)

// Same tier palette referenced in `Poster.stories.tsx` and originally from
// `openamer-account-service/src/app/manage-subscription/_components/TierCard.tsx`.
// Keep the two in sync so a design review can compare the card layout and
// the bare poster side-by-side.
const TIERS = [
  {
    bullets: ['Free models only'],
    label: 'Scout',
    price: { primary: 'Free', primarySuffix: '/mo' },
    src: SCOUT_SRC,
    tint: '#88ccaa'
  },
  {
    bullets: ['300+ models', 'Hosted tool usage', '$5 monthly credits'],
    label: 'Visor',
    price: { primary: '$5', primarySuffix: '/mo' },
    src: '/img/openamer-2.png',
    tint: '#99bbdd'
  },
  {
    bullets: [
      '300+ models',
      'Hosted tool usage',
      '$20 monthly credits',
      '$40 rollover cap'
    ],
    label: 'Angel',
    price: { primary: '$20', primarySuffix: '/mo' },
    src: '/img/openamer-3.jpg',
    tint: '#ccaa88'
  },
  {
    bullets: [
      '300+ models',
      'Hosted tool usage',
      '$50 monthly credits',
      '$100 rollover cap'
    ],
    label: 'Herald',
    price: { primary: '$50', primarySuffix: '/mo' },
    src: '/img/openamer-4.png',
    tint: '#dd8899'
  },
  {
    bullets: [
      '300+ models',
      'Hosted tool usage',
      '$150 monthly credits',
      '$300 rollover cap'
    ],
    label: 'Muse',
    price: { primary: '$200', primarySuffix: '/mo' },
    src: '/img/openamer-1.png',
    tint: '#ccaa88'
  }
] as const

const HIGHEST_OVERLAY = {
  overlay: 'rgba(180, 30, 20, 1)',
  tint: '#ff4444',
  tintStrength: { active: 0.55, inactive: 0.35 }
}

const meta = {
  args: {
    bullets: [...TIERS[2].bullets],
    image: TIERS[2].src,
    price: TIERS[2].price,
    tint: TIERS[2].tint,
    title: TIERS[2].label
  },
  argTypes: {
    badge: { control: 'text' },
    bullets: { control: 'object' },
    className: { table: { disable: true } },
    image: { control: 'text' },
    isCurrent: { control: 'boolean' },
    onSelect: { action: 'select' },
    overlay: { control: 'color' },
    price: { control: 'object' },
    selected: { control: 'boolean' },
    tint: { control: 'color' },
    tintStrength: { control: 'object' },
    title: { control: 'text' }
  },
  component: TierCard,
  decorators: [
    (Story, context) => {
      // Stories that provide their own layout (e.g. `Row`) opt in via the
      // `tierCardRaw` param. Everything else gets the compact 16rem preview
      // frame on top of the dark background lens.
      if (context.parameters?.tierCardRaw) {
        return <Story />
      }

      return (
        <div
          className="bg-background flex items-center justify-center p-8"
          style={{ minHeight: '100dvh' }}
        >
          <div className="w-[22rem]">
            <Story />
          </div>
        </div>
      )
    }
  ],
  parameters: {
    docs: {
      description: {
        component:
          'Selectable subscription-tier card. Fully presentational: the consumer owns the data (tier schema, price formatting, imagery, tints). Toggle `selected` to see the `.arc-border` shimmer and `mix-blend-mode: plus-lighter` lift on the headline / price.'
      }
    },
    layout: 'fullscreen'
  },
  title: 'Components/Data Display/TierCard'
} satisfies Meta<typeof TierCard>

export default meta

type Story = StoryObj<typeof meta>

/** Default resting state. Hover to preview the arc-border shimmer. */
export const Idle: Story = {}

/** Selected state — arc-border, active distortion, lifted text. */
export const Selected: Story = {
  args: { selected: true }
}

/** Current plan, not selected — subtle midground border hint. */
export const Current: Story = {
  args: { badge: '(current)', isCurrent: true }
}

/** Current plan AND selected — both treatments compose. */
export const CurrentSelected: Story = {
  args: { badge: '(current)', isCurrent: true, selected: true }
}

/** Highest tier red-overlay treatment. */
export const HighestTier: Story = {
  args: {
    ...HIGHEST_OVERLAY,
    bullets: [...TIERS[3].bullets],
    image: TIERS[3].src,
    price: { primary: '$200', primarySuffix: '/mo' },
    selected: true,
    title: 'Sovereign'
  }
}

/** Struck-through comparison price (e.g. first-payment discount). */
export const WithDiscount: Story = {
  args: {
    bullets: [...TIERS[2].bullets],
    image: TIERS[2].src,
    price: {
      primary: '$10',
      primarySuffix: 'first payment',
      secondary: '$20',
      secondarySuffix: '/mo'
    },
    tint: TIERS[2].tint,
    title: TIERS[2].label
  }
}

/**
 * Full 5-card row approximating the live manage-subscription page, with
 * the highest tier carrying the red overlay. Click any card to toggle
 * selection — mirrors the interaction model in the consumer app.
 */
export const Row: StoryObj = {
  // Opt out of the compact single-card wrapper (see the meta decorator)
  // and supply a full-width grid instead.
  decorators: [
    Story => (
      <div
        className="bg-background flex items-center justify-center p-10"
        style={{ minHeight: '100dvh' }}
      >
        <div className="grid w-full max-w-[90rem] grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <Story />
        </div>
      </div>
    )
  ],
  parameters: { layout: 'fullscreen', tierCardRaw: true },
  render: () => (
    <>
      {TIERS.map((tier, i) => {
        const isHighest = i === TIERS.length - 1

        return (
          <TierCard
            bullets={[...tier.bullets]}
            image={tier.src}
            key={tier.label}
            price={tier.price}
            selected={i === 2}
            title={tier.label}
            {...(isHighest ? HIGHEST_OVERLAY : { tint: tier.tint })}
          />
        )
      })}
    </>
  )
}
