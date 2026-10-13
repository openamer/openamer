'use client'

import { AnimatePresence, motion } from 'motion/react'
import { createElement, useCallback, useRef, useState } from 'react'

import { useCssVarDims } from '../hooks/use-css-var-dims'
import { useGpuTier } from '../hooks/use-gpu-tier'
import { cn } from '../utils'

import { Blink } from './components/blink'
import { Cell, Grid } from './components/grid'
import { HoverBg } from './components/hover-bg'
import { HamburgerIcon } from './components/icons/hamburger'
import { Scramble } from './components/scramble'
import { Socials, type SocialLink } from './components/socials'
import { ThemeToggle } from './components/theme-toggle'
import { H2 } from './components/typography/h2'
import { Small } from './components/typography/small'

const DEFAULT_BRAND = (
  <hgroup className="flex flex-col gap-2">
    <Small>OpenAmer</Small>

    <H2>Research</H2>
  </hgroup>
)

const DEFAULT_LINKS: HeaderLink[] = [
  { href: '/projects', label: 'Projects' },
  { href: '/participants', label: 'Participants' },
  { href: '/provenance', label: 'Provenance' },
  { href: '/contribute', label: 'Contribute' }
]

export function Header({
  brand = DEFAULT_BRAND,
  brandHref = '/',
  className,
  desktopGridStyle,
  links = DEFAULT_LINKS,
  LinkComponent = 'a',
  scramble: scrambleProp = true,
  socials,
  socialsLabel = 'Socials',
  style,
  themeLabel = 'Theme',
  themeToggle = false
}: HeaderProps) {
  const ref = useRef<HTMLElement>(null)
  useCssVarDims('header', ref)

  // Skip the hover-Scramble rAF loop on tier-0 devices (no GPU / software
  // renderer / `prefers-reduced-motion: reduce`) regardless of the prop.
  const gpuTier = useGpuTier()
  const scramble = scrambleProp && gpuTier > 0

  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])

  const hasSocials = (socials?.length ?? 0) > 0
  const hasMobileChrome = themeToggle || hasSocials

  return (
    <header className={className} ref={ref} style={style}>
      <Grid
        className="hidden border-t border-b lg:grid"
        style={desktopGridStyle}
      >
        <BrandCell
          brand={brand}
          href={brandHref}
          LinkComponent={LinkComponent}
        />

        {links.map(link => (
          <NavCell
            key={link.href}
            link={link}
            LinkComponent={LinkComponent}
            scramble={scramble}
          />
        ))}

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

      <div
        className={cn(
          'flex items-center justify-between border border-current/20 p-4',
          'lg:hidden'
        )}
      >
        <BrandLink
          brand={brand}
          href={brandHref}
          LinkComponent={LinkComponent}
        />

        <div className="flex items-center gap-3">
          {themeToggle && <ThemeToggle />}

          <button
            aria-label={open ? 'Close menu' : 'Open menu'}
            className="relative z-50 cursor-pointer bg-transparent p-2"
            onClick={() => setOpen(v => !v)}
            type="button"
          >
            <HamburgerIcon open={open} />
          </button>
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            animate={{ opacity: 1 }}
            className={cn(
              'bg-background/95 fixed inset-0 z-50 flex flex-col backdrop-blur-sm',
              'p-8 lg:hidden'
            )}
            exit={{ opacity: 0 }}
            initial={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="flex flex-col border border-current/20">
              <div className="flex items-center justify-between border-b border-current/20 p-4">
                <BrandLink
                  brand={brand}
                  href={brandHref}
                  LinkComponent={LinkComponent}
                  onClick={close}
                />

                <button
                  aria-label="Close menu"
                  className="cursor-pointer bg-transparent p-2"
                  onClick={close}
                  type="button"
                >
                  <HamburgerIcon open />
                </button>
              </div>

              {links.map(link => (
                <MobileNavLink
                  key={link.href}
                  link={link}
                  LinkComponent={LinkComponent}
                  onNavigate={close}
                  scramble={scramble}
                />
              ))}

              {hasMobileChrome && (
                <div className="flex items-center gap-3 border-b border-current/20 p-4">
                  {hasSocials && (
                    <>
                      <Small className="opacity-50">{socialsLabel}</Small>

                      <Socials items={socials!} onNavigate={close} />
                    </>
                  )}

                  {themeToggle && hasSocials && <span className="flex-1" />}

                  {themeToggle && (
                    <>
                      <Small className="opacity-50">{themeLabel}</Small>

                      <ThemeToggle />
                    </>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}

function BrandCell({ brand, href, LinkComponent }: BrandSlotProps) {
  return isExternal(href) ? (
    <Cell href={href} {...EXTERNAL_REL} as="a">
      {brand}
    </Cell>
  ) : (
    <Cell as={LinkComponent} href={href}>
      {brand}
    </Cell>
  )
}

function BrandLink({ brand, href, LinkComponent, onClick }: BrandLinkProps) {
  if (isExternal(href)) {
    return (
      <a href={href} onClick={onClick} {...EXTERNAL_REL}>
        {brand}
      </a>
    )
  }

  return createElement(
    LinkComponent,
    { href, onClick } as Record<string, unknown>,
    brand
  )
}

function NavCell({ link, LinkComponent, scramble }: NavCellProps) {
  const ref = useRef<HTMLAnchorElement>(null)
  const isExt = link.external ?? isExternal(link.href)

  const inner = (
    <>
      <Small>
        {scramble ? (
          <Scramble target={ref}>{link.label}</Scramble>
        ) : (
          link.label
        )}

        <Blink />
      </Small>

      <HoverBg />
    </>
  )

  if (isExt) {
    return (
      <Cell
        as="a"
        className="group relative cursor-pointer"
        href={link.href}
        onClick={link.onClick}
        ref={ref}
        {...EXTERNAL_REL}
      >
        {inner}
      </Cell>
    )
  }

  return (
    <Cell
      as={LinkComponent}
      className="group relative cursor-pointer"
      href={link.href}
      onClick={link.onClick}
      ref={ref}
    >
      {inner}
    </Cell>
  )
}

function MobileNavLink({
  link,
  LinkComponent,
  onNavigate,
  scramble
}: MobileNavLinkProps) {
  const ref = useRef<HTMLAnchorElement>(null)
  const isExt = link.external ?? isExternal(link.href)

  const className = cn(
    'group relative flex cursor-pointer items-center border-b border-current/20 p-4'
  )

  const onClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    link.onClick?.(e)
    onNavigate()
  }

  const children = (
    <>
      <Small>
        {scramble ? (
          <Scramble target={ref}>{link.label}</Scramble>
        ) : (
          link.label
        )}

        <Blink />
      </Small>

      <HoverBg />
    </>
  )

  if (isExt) {
    return (
      <a
        className={className}
        href={link.href}
        onClick={onClick}
        ref={ref}
        {...EXTERNAL_REL}
      >
        {children}
      </a>
    )
  }

  return createElement(
    LinkComponent,
    { className, href: link.href, onClick, ref } as Record<string, unknown>,
    children
  )
}

const EXTERNAL_REL = {
  rel: 'noopener noreferrer',
  target: '_blank'
} as const

const isExternal = (href: string) => /^(https?:|mailto:|tel:)/i.test(href)

interface BrandLinkProps extends BrandSlotProps {
  onClick?: React.MouseEventHandler
}

interface BrandSlotProps {
  brand: React.ReactNode
  href: string
  LinkComponent: React.ElementType
}

export interface HeaderLink {
  external?: boolean
  href: string
  label: string
  onClick?: React.MouseEventHandler
}

export interface HeaderProps {
  brand?: React.ReactNode
  brandHref?: string
  className?: string
  /**
   * Inline `style` for the desktop `Grid` only — useful for overriding
   * `grid-template-columns` (e.g. to align with a sidebar track) without
   * affecting the mobile bar or drawer.
   */
  desktopGridStyle?: React.CSSProperties
  links?: HeaderLink[]
  LinkComponent?: React.ElementType
  /**
   * Apply the hover-Scramble effect to nav link labels. Defaults to `true`,
   * automatically suppressed on tier-0 GPUs and when the user has
   * `prefers-reduced-motion: reduce`.
   */
  scramble?: boolean
  /**
   * Optional socials shown in a trailing chrome cell on desktop and in the
   * mobile drawer's chrome row. For nav-heavy products (≥ 5 links) prefer
   * passing socials to `<Footer>` instead — the desktop `Grid` only ships
   * column rules through `grid-cols-6`, so brand + many links + chrome can
   * overflow.
   */
  socials?: SocialLink[]
  socialsLabel?: string
  style?: React.CSSProperties
  themeLabel?: string
  themeToggle?: boolean
}

/** @deprecated Use `SocialLink` from `@openamer-research/ui`. Same shape. */
export type HeaderSocial = SocialLink

interface MobileNavLinkProps {
  link: HeaderLink
  LinkComponent: React.ElementType
  onNavigate: () => void
  scramble: boolean
}

interface NavCellProps {
  link: HeaderLink
  LinkComponent: React.ElementType
  scramble: boolean
}
