// Upstream-Derived: apps/desktop/src/components/chat/intro.tsx @ e026fd61d (MIT)
import { type CSSProperties, useState } from 'react'

import { useI18n } from '@/i18n'
import type { IntroCopyBlock, IntroPersona } from '@/i18n/types'
import { capitalize, normalize } from '@/lib/text'

type IntroCopy = {
  headline: string
  body: string
}

export type IntroProps = {
  personality?: string
  seed?: number
}

const NEUTRAL_PERSONALITIES = new Set(['', 'default', 'none', 'neutral'])

function normalizeKey(value?: string): string {
  return normalize(value)
}

function titleize(value: string): string {
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map(capitalize)
    .join(' ')
}

function isPersona(key: string, personas: Record<string, IntroCopyBlock>): key is IntroPersona {
  return Object.prototype.hasOwnProperty.call(personas, key)
}

/** Turn one translated block into the parallel {headline, body} entries the UI picks from. */
function toCopies(block: IntroCopyBlock | undefined): IntroCopy[] {
  if (!block || block.headlines.length === 0) {
    return []
  }

  return block.headlines.map((headline, index) => ({
    headline,
    body: block.bodies[index] ?? headline
  }))
}

function withLabel(template: string, label: string): string {
  return template.replaceAll('${label}', label)
}

function personaModeCopies(block: IntroCopyBlock, label: string): IntroCopy[] {
  return block.headlines.map((headline, index) => ({
    headline: withLabel(headline, label),
    body: withLabel(block.bodies[index] ?? headline, label)
  }))
}

function pickCopy(copies: IntroCopy[], seed = 0): IntroCopy | undefined {
  return copies[Math.abs(seed) % copies.length]
}

const WORDMARK = 'OPENAMER AGENT'

export function Intro({ personality, seed }: IntroProps) {
  const { t } = useI18n()
  const [mountSeed] = useState(() => Math.floor(Math.random() * 100000))

  const intro = t.intro
  const personalityKey = normalizeKey(personality)
  const neutralKey = NEUTRAL_PERSONALITIES.has(personalityKey) ? 'none' : personalityKey

  // A translated block for this personality, else the neutral block, else the
  // translated fallback lines. The persona-mode templates keep an unknown
  // personality name visible instead of silently dropping it.
  const copies = isPersona(neutralKey, intro.personas) ? toCopies(intro.personas[neutralKey]) : toCopies(intro.fallback)

  const resolved =
    copies.length > 0 ? copies : personaModeCopies(intro.personaMode, titleize(neutralKey) || titleize('default'))

  const copy = pickCopy(resolved, mountSeed + (seed ?? 0)) ?? {
    headline: WORDMARK,
    body: ''
  }

  return (
    <div
      className="pointer-events-none flex w-full min-w-0 flex-col items-center justify-center px-0.5 py-6 text-center text-muted-foreground sm:px-6 lg:px-8"
      data-slot="aui_intro"
    >
      <div className="w-full min-w-0">
        <p
          aria-label={WORDMARK}
          className="fit-text mx-auto mb-1 w-[calc(100%-1rem)] font-['Collapse'] font-bold uppercase leading-[0.9] tracking-[0.08em] text-midground mix-blend-plus-lighter dark:text-foreground/90"
          style={{ '--fit-min': '2.75rem' } as CSSProperties}
        >
          <span>
            <span>{WORDMARK}</span>
          </span>
          <span aria-hidden="true">{WORDMARK}</span>
        </p>

        <p className="m-0 text-center leading-normal tracking-tight">{copy.body}</p>
      </div>
    </div>
  )
}
