import type { Meta, StoryObj } from '@storybook/react-vite'

import fillerBg from '../../assets/filler-bg0.webp'
import { Poster } from './poster'

import type { ComponentProps } from 'react'

// Triptych-scoped story type: the gallery/triptych renders thread a
// `showLabels` toggle through the Controls panel that isn't a Poster prop.
type TriptychArgs = ComponentProps<typeof Poster> & { showLabels?: boolean }
type TriptychStory = StoryObj<TriptychArgs>

const SCOUT_SRC = fillerBg.src ?? (fillerBg as unknown as string)

// Matches the tier visuals from openamer-account-service/src/app/manage-subscription/_components/TierCard.tsx
const TIERS = [
  {
    label: 'Scout',
    src: SCOUT_SRC,
    subtitle: 'warrior approaches the giant',
    tint: '#88ccaa'
  },
  {
    label: 'Visor',
    src: '/img/openamer-2.png',
    subtitle: 'helmeted figure, visor drawn',
    tint: '#99bbdd'
  },
  {
    label: 'Angel',
    src: '/img/openamer-3.jpg',
    subtitle: 'winged, in flight',
    tint: '#ccaa88'
  },
  {
    label: 'Herald',
    src: '/img/openamer-4.png',
    subtitle: 'plumed helm, armored',
    tint: '#dd8899'
  },
  {
    label: 'Muse',
    src: '/img/openamer-1.png',
    subtitle: 'portrait, pensive',
    tint: '#ccaa88'
  }
] as const

const HIGHEST_TINT = '#ff4444'
const HIGHEST_TINT_STRENGTH = { active: 0.55, inactive: 0.35 }

const meta: Meta<typeof Poster> = {
  argTypes: {
    aspect: {
      control: 'select',
      options: ['square', 'portrait', 'landscape', 'story', 'wide']
    },
    autoPlay: {
      control: 'select',
      options: ['slash', 'gentle', 'aggressive']
    },
    // `React.ReactNode` props default to Storybook's "object" control, which
    // shows as "Set object" and can't be edited in-place. Force them to
    // plain text / object inputs since that's how they're used in practice.
    body: {
      control: 'text',
      table: { category: 'Dispatch variant' }
    },
    border: { control: 'boolean' },
    channel: { control: 'text' },
    // `children` and `className` are dev-only escape hatches (arbitrary JSX
    // / Tailwind passthrough). Neither is useful for the "record a GIF for
    // socials" workflow, so hide them from the panel to keep it tidy.
    children: { table: { disable: true } },
    className: { table: { disable: true } },
    cornerMarks: { control: 'boolean' },
    eyebrow: {
      control: 'text',
      table: { category: 'Dispatch variant' }
    },
    headline: {
      control: 'object',
      table: { category: 'Dispatch variant' }
    },
    layout: {
      control: 'inline-radio',
      options: ['split', 'stacked'],
      table: { category: 'Dispatch variant' }
    },
    scale: { control: { max: 1, min: 0.25, step: 0.05, type: 'range' } },
    seal: {
      control: 'text',
      table: { category: 'Dispatch variant' }
    },
    signature: { control: 'text' },
    src: { control: 'text' },
    tags: {
      control: 'object',
      table: { category: 'Dispatch variant' }
    },
    tint: { control: 'color' },
    tintStrength: { control: 'object' },
    variant: {
      control: 'inline-radio',
      options: ['vibe', 'dispatch']
    }
  },
  component: Poster,
  parameters: {
    docs: {
      description: {
        component:
          'A social-ready glitchy card built around the haptic-distortion image component. Defaults to the `vibe` variant — full-bleed distortion with minimal registration chrome — matching the overlay on the OpenAmer agent website. Switch to `variant="dispatch"` for the broadcast-card layout with copy + sidebar tags.\n\nPoster stories include all five tier images from the `manage-subscription` page so you can screen-record any character on-demand.'
      }
    },
    layout: 'centered'
  },
  title: 'Components/Data Display/Poster'
}

export default meta

type Story = StoryObj<typeof Poster>

/**
 * Primary story. Full-bleed "Scout" scene (warrior approaching the giant),
 * minimal chrome, just the subtle `OpenAmer Agent` overlay at the bottom-right.
 * Screen-record one ~7s pass (two 3.6s slash cycles) → export as GIF →
 * attach to the pricing tweet.
 *
 * Rendered at full target resolution (1080×1080). The storybook viewport
 * naturally clamps it via `max-width: 100%` if your window is narrower.
 */
export const Vibe: Story = {
  args: {
    aspect: 'square',
    autoPlay: 'slash',
    scale: 1,
    signature: 'OpenAmer Agent',
    variant: 'vibe'
  }
}

/** 9:16 for Instagram / TikTok stories and reels. */
export const VibeStory: Story = {
  args: {
    aspect: 'story',
    autoPlay: 'slash',
    scale: 1,
    signature: 'OpenAmer Agent',
    variant: 'vibe'
  },
  name: 'Vibe · Story (9:16)'
}

/** 16:9 for Twitter cards, LinkedIn, Discord embeds. */
export const VibeLandscape: Story = {
  args: {
    aspect: 'landscape',
    autoPlay: 'slash',
    scale: 1,
    signature: 'OpenAmer Agent',
    variant: 'vibe'
  },
  name: 'Vibe · Landscape (16:9)'
}

/** 4:5 — the Instagram feed recommendation. */
export const VibePortrait: Story = {
  args: {
    aspect: 'portrait',
    autoPlay: 'slash',
    scale: 1,
    signature: 'OpenAmer Agent',
    variant: 'vibe'
  },
  name: 'Vibe · Portrait (4:5)'
}

// ─── Tier images, each on its canonical tint ───

/**
 * All five `manage-subscription` tier images in one view, each with the
 * tint from `TierCard.tsx`. Pick whichever one matches the vibe for the
 * release and screen-record it on its own.
 */
export const TierGallery: TriptychStory = {
  args: {
    aspect: 'square',
    autoPlay: 'slash',
    border: true,
    cornerMarks: true,
    scale: 0.3,
    showLabels: true,
    variant: 'vibe'
  },
  argTypes: { showLabels: { control: 'boolean' } },
  name: 'Tier Gallery',
  parameters: { layout: 'fullscreen' },
  render: ({ showLabels, ...args }) => (
    <div className="bg-background flex min-h-screen items-center justify-center p-8">
      <div className="grid grid-cols-3 items-start gap-4 xl:grid-cols-5">
        {TIERS.map(tier => (
          <div className="flex flex-col gap-2" key={tier.label}>
            {showLabels && (
              <div className="flex items-baseline justify-between gap-2 px-1">
                <span className="font-mondwest text-[0.75rem] tracking-[0.1875rem] uppercase opacity-80">
                  {tier.label}
                </span>

                <span className="font-courier text-[0.625rem] tracking-widest opacity-40">
                  {tier.tint}
                </span>
              </div>
            )}

            <Poster
              {...args}
              signature={showLabels ? tier.label : undefined}
              src={tier.src}
              tint={tier.tint}
            />

            {showLabels && (
              <span className="font-courier px-1 text-[0.625rem] tracking-wider opacity-50">
                {tier.subtitle}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export const TierScout: Story = {
  args: {
    aspect: 'square',
    autoPlay: 'slash',
    scale: 1,
    signature: 'OpenAmer Agent',
    src: SCOUT_SRC,
    tint: TIERS[0].tint,
    variant: 'vibe'
  },
  name: 'Tier · Scout'
}

export const TierVisor: Story = {
  args: {
    aspect: 'square',
    autoPlay: 'slash',
    scale: 1,
    signature: 'OpenAmer Agent',
    src: TIERS[1].src,
    tint: TIERS[1].tint,
    variant: 'vibe'
  },
  name: 'Tier · Visor'
}

export const TierAngel: Story = {
  args: {
    aspect: 'square',
    autoPlay: 'gentle',
    scale: 1,
    signature: 'OpenAmer Agent',
    src: TIERS[2].src,
    tint: TIERS[2].tint,
    variant: 'vibe'
  },
  name: 'Tier · Angel'
}

export const TierHerald: Story = {
  args: {
    aspect: 'square',
    autoPlay: 'slash',
    scale: 1,
    signature: 'OpenAmer Agent',
    src: TIERS[3].src,
    tint: TIERS[3].tint,
    variant: 'vibe'
  },
  name: 'Tier · Herald'
}

export const TierMuse: Story = {
  args: {
    aspect: 'square',
    autoPlay: 'gentle',
    scale: 1,
    signature: 'OpenAmer Agent',
    src: TIERS[4].src,
    tint: TIERS[4].tint,
    variant: 'vibe'
  },
  name: 'Tier · Muse'
}

/**
 * Top-tier red-overlay treatment from `TierCard` — use this for the
 * "Sovereign" / highest tier poster.
 */
export const TierApex: Story = {
  args: {
    aspect: 'square',
    autoPlay: 'aggressive',
    scale: 1,
    signature: 'OpenAmer · Apex',
    src: TIERS[3].src,
    tint: HIGHEST_TINT,
    tintStrength: HIGHEST_TINT_STRENGTH,
    variant: 'vibe'
  },
  name: 'Tier · Apex (highest)'
}

/** Three vibe tiles side-by-side — same scene, three tier tints. */
export const VibeTriptychScout: TriptychStory = {
  args: {
    aspect: 'square',
    autoPlay: 'slash',
    border: true,
    cornerMarks: true,
    scale: 0.35,
    showLabels: true,
    variant: 'vibe'
  },
  argTypes: { showLabels: { control: 'boolean' } },
  name: 'Vibe · Triptych (Scout, 3 tints)',
  parameters: { layout: 'fullscreen' },
  // `args` here drives the shared props across all three tiles; per-tile
  // specifics (signature, tint) stay hardcoded inside the render so the
  // triptych keeps its identity while you tweak chrome/scale/etc. from the
  // Controls panel. `showLabels` hides the per-tile signature text.
  render: ({ showLabels, ...args }) => (
    <div className="bg-background flex min-h-screen items-center justify-center p-8">
      <div className="flex items-stretch gap-4">
        <Poster
          {...args}
          signature={showLabels ? 'Studio' : undefined}
          tint="#88ccaa"
        />

        <Poster
          {...args}
          signature={showLabels ? 'Pro' : undefined}
          tint="#ccaa88"
        />

        <Poster
          {...args}
          signature={showLabels ? 'Sovereign' : undefined}
          tint={HIGHEST_TINT}
          tintStrength={HIGHEST_TINT_STRENGTH}
        />
      </div>
    </div>
  )
}

/** Three vibe tiles, three tier images — mixed character set. */
export const VibeTriptychMixed: TriptychStory = {
  args: {
    aspect: 'square',
    autoPlay: 'slash',
    border: true,
    cornerMarks: true,
    scale: 0.35,
    showLabels: true,
    variant: 'vibe'
  },
  argTypes: { showLabels: { control: 'boolean' } },
  name: 'Vibe · Triptych (mixed characters)',
  parameters: { layout: 'fullscreen' },
  render: ({ showLabels, ...args }) => (
    <div className="bg-background flex min-h-screen items-center justify-center p-8">
      <div className="flex items-stretch gap-4">
        <Poster
          {...args}
          signature={showLabels ? TIERS[0].label : undefined}
          src={TIERS[0].src}
          tint={TIERS[0].tint}
        />

        <Poster
          {...args}
          signature={showLabels ? TIERS[2].label : undefined}
          src={TIERS[2].src}
          tint={TIERS[2].tint}
        />

        <Poster
          {...args}
          signature={showLabels ? TIERS[3].label : undefined}
          src={TIERS[3].src}
          tint={HIGHEST_TINT}
          tintStrength={HIGHEST_TINT_STRENGTH}
        />
      </div>
    </div>
  )
}

/** "Gentle" choreography — softer, slower drift. */
export const VibeGentle: Story = {
  args: {
    aspect: 'square',
    autoPlay: 'gentle',
    scale: 1,
    signature: 'OpenAmer Agent',
    tint: '#88ccaa',
    variant: 'vibe'
  }
}

/** "Aggressive" choreography — rapid multi-directional stabs. */
export const VibeAggressive: Story = {
  args: {
    aspect: 'square',
    autoPlay: 'aggressive',
    scale: 1,
    signature: 'OpenAmer Agent',
    tint: HIGHEST_TINT,
    variant: 'vibe'
  }
}

// ─── Dispatch variants (in the backpocket if copy ends up on the poster) ───

/** Full broadcast-card layout with copy, sidebar tags, and chrome. */
export const DispatchPricingTeaser: Story = {
  args: {
    aspect: 'square',
    body: 'New tiers. Same autonomous agent, scaled to how you actually run it — solo on a laptop, shared across a team, or sovereign on your own hardware.',
    channel: 'OPENAMER • OPENAMER AGENT',
    eyebrow: 'PRICING / 2026',
    headline: ['Pricing', 'That Grows', 'With You.'],
    scale: 1,
    seal: 'v0.9 · 2026',
    signature: 'openamerresearch.com/openamer-agent',
    tags: ['Studio · free', 'Pro · $20/mo', 'Sovereign · on-prem'],
    tint: '#ccaa88',
    variant: 'dispatch'
  },
  name: 'Dispatch · Pricing Teaser'
}

/** Three dispatch posters side-by-side for the full tier rollout. */
export const DispatchTriptych: TriptychStory = {
  args: {
    aspect: 'square',
    border: true,
    cornerMarks: true,
    scale: 0.35,
    showLabels: true,
    variant: 'dispatch'
  },
  argTypes: { showLabels: { control: 'boolean' } },
  name: 'Dispatch · Triptych',
  parameters: { layout: 'fullscreen' },
  render: ({ showLabels, ...args }) => (
    <div className="bg-background flex min-h-screen items-center justify-center p-8">
      <div className="flex items-stretch gap-4">
        <Poster
          {...args}
          channel={showLabels ? 'OPENAMER • STUDIO' : undefined}
          eyebrow={showLabels ? 'TIER / 001' : undefined}
          headline={showLabels ? ['OpenAmer', 'Studio.'] : ['']}
          seal={showLabels ? 'FREE · MIT' : undefined}
          signature={showLabels ? 'openamer.run / studio' : undefined}
          src={TIERS[0].src}
          tags={showLabels ? ['Local-first', 'Unlimited tools', 'MIT'] : []}
          tint={TIERS[0].tint}
        />

        <Poster
          {...args}
          channel={showLabels ? 'OPENAMER • PRO' : undefined}
          eyebrow={showLabels ? 'TIER / 002' : undefined}
          headline={showLabels ? ['OpenAmer', 'Pro.'] : ['']}
          seal={showLabels ? '$20/mo' : undefined}
          signature={showLabels ? 'openamer.run / pro' : undefined}
          src={TIERS[2].src}
          tags={
            showLabels
              ? ['Hosted memory', 'Priority inference', 'Team workspaces']
              : []
          }
          tint={TIERS[2].tint}
        />

        <Poster
          {...args}
          channel={showLabels ? 'OPENAMER • SOVEREIGN' : undefined}
          eyebrow={showLabels ? 'TIER / 003' : undefined}
          headline={showLabels ? ['OpenAmer', 'Sovereign.'] : ['']}
          seal={showLabels ? 'talk to us' : undefined}
          signature={showLabels ? 'openamer.run / sovereign' : undefined}
          src={TIERS[3].src}
          tags={
            showLabels
              ? ['Self-hosted', 'Dedicated inference', 'SSO + audit']
              : []
          }
          tint={HIGHEST_TINT}
          tintStrength={HIGHEST_TINT_STRENGTH}
        />
      </div>
    </div>
  )
}
