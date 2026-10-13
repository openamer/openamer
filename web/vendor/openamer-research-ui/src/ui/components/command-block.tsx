'use client'

import { useCallback, useState } from 'react'

import { cn } from '../../utils'

import { Small } from './typography/small'

/**
 * A "copy to clipboard" button that briefly shows a "Copied!" confirmation.
 * Designed to sit alongside a short command string, not as a general button.
 */
export function CopyButton({
  children,
  className,
  copiedLabel = 'Copied!',
  label = 'Copy',
  resetDelayMs = 2000,
  text
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), resetDelayMs)
    })
  }, [resetDelayMs, text])

  return (
    <button
      className={cn(
        'font-courier text-display cursor-pointer border-none bg-transparent text-xs',
        'tracking-widest',
        'hover:text-midground tap-highlight-transparent transition-colors',
        'flex items-center justify-center',
        copied ? 'text-midground' : 'text-text-secondary',
        className
      )}
      onClick={handleCopy}
      type="button"
    >
      {children ?? (copied ? copiedLabel : label)}
    </button>
  )
}

/**
 * A labeled, copy-able command (or code) display. Pairs `<CopyButton>` with
 * a monospace code block. Used for install/setup instructions.
 */
export function CommandBlock({ className, code, label }: CommandBlockProps) {
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div className="flex items-center justify-between">
        <Small className="opacity-50">{label}</Small>

        <CopyButton text={code} />
      </div>

      <div
        className={cn(
          'bg-background/40 font-courier border border-current/20',
          'px-3 py-2 text-[0.6875rem] leading-relaxed lowercase'
        )}
      >
        <code className="break-all">{code}</code>
      </div>
    </div>
  )
}

interface CommandBlockProps {
  className?: string
  code: string
  label: string
}

interface CopyButtonProps {
  children?: React.ReactNode
  className?: string
  copiedLabel?: string
  label?: string
  resetDelayMs?: number
  text: string
}
