'use client'

import { useEffect, useRef, useState } from 'react'

const BLOCK = '░▒▓█▄▀▐▌─│┌┐└┘├┤┬┴┼╌╎⣀⣤⣶⣿'
const ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%&*'

const rand = (chars: string) => chars[(Math.random() * chars.length) | 0]

export function Scramble({
  delay = 0,
  text
}: {
  delay?: number
  text: string
}) {
  const [display, setDisplay] = useState(text)
  const iter = useRef(0)

  useEffect(() => {
    iter.current = 0

    const timeout = setTimeout(() => {
      const interval = setInterval(() => {
        setDisplay(
          text
            .split('')
            .map((c, i) =>
              c === ' ' ? ' ' : i < iter.current ? text[i] : rand(ALPHA)
            )
            .join('')
        )

        iter.current += 1 / 3

        if (iter.current >= text.length) {
          clearInterval(interval)
          setDisplay(text)
        }
      }, 30)

      return () => clearInterval(interval)
    }, delay)

    return () => clearTimeout(timeout)
  }, [text, delay])

  return <>{display}</>
}

export function AsciiSkeleton({
  className = '',
  cols = 12,
  rows = 1,
  speed = 80
}: {
  className?: string
  cols?: number
  rows?: number
  speed?: number
}) {
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const el = ref.current

    if (!el) {
      return
    }

    const total = cols * rows
    let frame = 0

    const tick = () => {
      let text = ''

      for (let i = 0; i < total; i++) {
        const x = i % cols
        const shimmer = (x - frame * 0.5 + cols * 2) % (cols * 2)

        text += shimmer < 6 ? ' ' : rand(BLOCK)

        if (rows > 1 && x === cols - 1) {
          text += '\n'
        }
      }

      el.textContent = text
      frame++
    }

    tick()
    const id = setInterval(tick, speed)

    return () => clearInterval(id)
  }, [cols, rows, speed])

  return (
    <span
      aria-hidden
      className={`inline-block leading-tight opacity-20 select-none ${className}`}
      ref={ref}
      style={{
        fontFamily: 'monospace',
        fontSize: 'inherit',
        letterSpacing: '0.05em'
      }}
    />
  )
}
