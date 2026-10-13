import { describe, expect, it, vi } from 'vitest'

import { guardStdioStream, installStdioGuards, isClosedPipeError } from './stdio-guard'

function makeStream() {
  const listeners: Record<string, ((...args: unknown[]) => void)[]> = {}

  return {
    listeners,
    on(event: string, listener: (...args: unknown[]) => void) {
      ;(listeners[event] ??= []).push(listener)

      return this
    },
    emitError(error: unknown) {
      for (const listener of listeners.error ?? []) {
        listener(error)
      }
    }
  }
}

describe('isClosedPipeError', () => {
  it('recognizes the codes a dead stdio pipe raises', () => {
    expect(isClosedPipeError({ code: 'EPIPE' })).toBe(true)
    expect(isClosedPipeError({ code: 'ERR_STREAM_DESTROYED' })).toBe(true)
    expect(isClosedPipeError({ code: 'ECONNRESET' })).toBe(true)
  })

  it('does not treat a real application error as a pipe failure', () => {
    expect(isClosedPipeError({ code: 'EACCES' })).toBe(false)
    expect(isClosedPipeError(new Error('boom'))).toBe(false)
    expect(isClosedPipeError('EPIPE')).toBe(false)
    expect(isClosedPipeError(null)).toBe(false)
    expect(isClosedPipeError(undefined)).toBe(false)
  })
})

describe('guardStdioStream', () => {
  it('swallows an EPIPE instead of letting it become fatal', () => {
    const stream = makeStream()
    guardStdioStream(stream)

    // Would throw "unhandled 'error' event" without the attached listener.
    expect(() => stream.emitError({ code: 'EPIPE' })).not.toThrow()
  })

  it('surfaces a non-pipe stream error on stderr', () => {
    const stream = makeStream()
    guardStdioStream(stream)
    const write = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)

    stream.emitError({ code: 'EACCES' })

    expect(write).toHaveBeenCalledOnce()
    expect(String(write.mock.calls[0][0])).toContain('stdio stream error')
    write.mockRestore()
  })

  it('does not throw when the reporting write itself fails', () => {
    const stream = makeStream()
    guardStdioStream(stream)

    const write = vi.spyOn(process.stderr, 'write').mockImplementation(() => {
      throw new Error('stderr is gone too')
    })

    expect(() => stream.emitError({ code: 'EACCES' })).not.toThrow()
    write.mockRestore()
  })

  it('is a no-op for a missing or malformed stream', () => {
    expect(() => guardStdioStream(null)).not.toThrow()
    expect(() => guardStdioStream(undefined)).not.toThrow()
    expect(() => guardStdioStream({} as never)).not.toThrow()
  })
})

describe('installStdioGuards', () => {
  it('attaches exactly one error handler per stdio stream, even when called twice', () => {
    const out = makeStream()
    const err = makeStream()
    const stdoutOn = vi.spyOn(process.stdout, 'on')
    const stderrOn = vi.spyOn(process.stderr, 'on')

    installStdioGuards()
    installStdioGuards()

    // Idempotent: the second call adds nothing.
    expect(stdoutOn).toHaveBeenCalledTimes(1)
    expect(stderrOn).toHaveBeenCalledTimes(1)

    stdoutOn.mockRestore()
    stderrOn.mockRestore()
    void out
    void err
  })
})
