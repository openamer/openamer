'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { cn } from '../../utils'

function sleep(ms: number) {
  return new Promise<void>(resolve => setTimeout(resolve, ms))
}

export function TerminalDemo({
  ariaLabel = 'Terminal Demo',
  className,
  height = 320,
  label = 'Terminal',
  loopDelayMs = 1000,
  outputLineDelayMs = 50,
  sequence
}: TerminalDemoProps) {
  const bodyRef = useRef<HTMLDivElement>(null)
  const startedRef = useRef(false)
  const [html, setHtml] = useState('')

  const runDemo = useCallback(async () => {
    if (startedRef.current) {
      return
    }

    startedRef.current = true
    let content = ''

    const render = (h: string) => {
      content = h
      setHtml(h)
    }

    for (;;) {
      for (const step of sequence) {
        switch (step.type) {
          case 'clear':
            content = ''
            render('')

            break

          case 'output':
            for (const line of step.lines) {
              render(content + '\n' + line)
              await sleep(outputLineDelayMs)
            }

            break

          case 'pause':
            await sleep(step.ms)

            break

          case 'prompt':
            render(content + `<span class="text-midground">${step.text}</span>`)

            break

          case 'type':
            for (const char of step.text) {
              render(content + char)
              await sleep(step.delay ?? 30)
            }

            break
        }
      }

      content = ''
      render('')
      await sleep(loopDelayMs)
    }
  }, [loopDelayMs, outputLineDelayMs, sequence])

  useEffect(() => {
    const el = bodyRef.current?.closest('[data-demo-root]')

    if (!el) {
      return
    }

    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            runDemo()
          }
        })
      },
      { threshold: 0.3 }
    )

    observer.observe(el)

    return () => observer.disconnect()
  }, [runDemo])

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight
    }
  }, [html])

  return (
    <div
      aria-label={ariaLabel}
      className={cn('border-4 border-double border-inherit', className)}
      data-demo-root
      role="img"
    >
      <div className="flex items-center gap-3 border-b border-current/10 px-3 py-2">
        <div className="flex gap-1.5">
          <span
            className="bg-midground size-2 rounded-full"
            style={{ mixBlendMode: 'plus-lighter' }}
          />

          <span className="bg-midground/60 size-2 rounded-full" />
          <span className="bg-midground/30 size-2 rounded-full" />
        </div>

        <span className="font-courier text-display text-xs tracking-widest text-text-tertiary">
          {label}
        </span>
      </div>

      <div
        className={cn(
          'overflow-x-hidden overflow-y-auto whitespace-pre-wrap',
          'font-courier p-4 text-[0.75rem] leading-[1.7] normal-case'
        )}
        dangerouslySetInnerHTML={{
          __html:
            html +
            '<span class="blink inline-block dither ml-0.5 h-[1em] w-[1ch]"></span>'
        }}
        ref={bodyRef}
        style={{ height }}
      />
    </div>
  )
}

interface ClearStep {
  type: 'clear'
}

interface OutputStep {
  lines: string[]
  type: 'output'
}

interface PauseStep {
  ms: number
  type: 'pause'
}

interface PromptStep {
  text: string
  type: 'prompt'
}

interface TerminalDemoProps {
  ariaLabel?: string
  className?: string
  height?: number | string
  label?: string
  loopDelayMs?: number
  outputLineDelayMs?: number
  sequence: TerminalDemoStep[]
}

export type TerminalDemoStep =
  | ClearStep
  | OutputStep
  | PauseStep
  | PromptStep
  | TypeStep

interface TypeStep {
  delay?: number
  text: string
  type: 'type'
}
