'use client'

import { useRef } from 'react'

import { useCssVarDims } from '../hooks/use-css-var-dims'
import { Cell, Grid } from './components/grid'
import { Socials, type SocialLink } from './components/socials'
import { ThemeToggle } from './components/theme-toggle'
import { Small } from './components/typography/small'

const DEFAULT_GROUPS: FooterGroup[] = [
  { label: 'Product', links: ['Overview', 'Features', 'Pricing'] },
  { label: 'Resources', links: ['Docs', 'Blog', 'Support'] },
  { label: 'Company', links: ['About', 'Careers', 'Contact'] },
  { label: 'Legal', links: ['Privacy', 'Terms', 'License'] }
]

export function Footer({
  className,
  groups = DEFAULT_GROUPS,
  LinkComponent = 'a',
  socials,
  socialsLabel = 'Socials',
  style,
  themeLabel = 'Theme',
  themeToggle = false
}: FooterProps) {
  const ref = useRef<HTMLElement>(null)
  useCssVarDims('footer', ref)

  const hasSocials = (socials?.length ?? 0) > 0
  const hasChrome = hasSocials || themeToggle

  return (
    <footer className={className} ref={ref} style={style}>
      <Grid>
        <Cell>
          <Small className="opacity-50">&copy;{new Date().getFullYear()}</Small>
        </Cell>

        {groups.map(({ label, links }) => (
          <Cell key={label}>
            <Small className="opacity-50">{label}</Small>

            <nav className="mt-3 flex flex-col gap-2">
              {links.map(link => {
                const href = typeof link === 'string'
                  ? `/${link.toLowerCase()}`
                  : link.href

                const label = typeof link === 'string' ? link : link.label

                return (
                  <Small
                    as={LinkComponent}
                    className="underline"
                    href={href}
                    key={label}
                  >
                    {label}
                  </Small>
                )
              })}
            </nav>
          </Cell>
        ))}
      </Grid>

      {hasChrome && (
        <Grid>
          {hasSocials && (
            <Cell className="flex items-start justify-between">
              <Small className="opacity-50">{socialsLabel}</Small>

              <Socials items={socials!} />
            </Cell>
          )}

          {themeToggle && (
            <Cell className="flex items-start justify-between">
              <Small className="opacity-50">{themeLabel}</Small>

              <ThemeToggle />
            </Cell>
          )}
        </Grid>
      )}
    </footer>
  )
}

export interface FooterGroup {
  label: string
  links: (FooterLink | string)[]
}

export interface FooterLink {
  href: string
  label: string
}

export interface FooterProps {
  className?: string
  groups?: FooterGroup[]
  LinkComponent?: React.ElementType
  socials?: SocialLink[]
  socialsLabel?: string
  style?: React.CSSProperties
  themeLabel?: string
  themeToggle?: boolean
}
