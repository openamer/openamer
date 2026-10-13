// Guard the main process against a closed stdio pipe.
//
// Electron's main process inherits the stdio of whoever launched it. On Windows
// that launcher can go away — the terminal that ran `openamer desktop` closes,
// the CI job's stdout is torn down, or a parent shell ends. The pipe is then
// dead, and the *next* `console.log` / `console.error` / `process.stdout.write`
// throws an unhandled `EPIPE: broken pipe, write`, which tears the whole main
// process down. That is a crash with no relation to what the app was doing —
// it fires on the next log line, however trivial — and it is exactly the shape
// a packaged desktop app must not have.
//
// The failure is not the log call; it is that the write's rejection has nobody
// to go to. Node surfaces a stream write error as an `'error'` event on the
// stream, and an unhandled `'error'` event on stdout/stderr is fatal. Attaching
// a no-op `'error'` handler to each stdio stream absorbs the EPIPE and lets the
// process keep running; the log line is lost, the app is not.
//
// This is deliberately narrow: it guards the *transport*, never swallows an
// application error. An `uncaughtException` handler would be the wrong tool —
// it would hide real bugs in the agent backend and renderer. We only silence
// the pipe.

export type StdioStreamLike = {
  on(event: string, listener: (...args: unknown[]) => void): unknown
  destroyed?: boolean
  writable?: boolean
}

// Errors that mean "the other end of this pipe is gone" rather than "the app is
// broken". EPIPE and ERR_STREAM_DESTROYED are the two Node raises when a write
// hits a closed/destroyed stdio pipe; ECONNRESET shows up when the reader is a
// socket-like console (a remote/pipe-backed host). Anything else is a genuine
// error and is left to surface.
const PIPE_GONE_CODES = new Set(['EPIPE', 'ERR_STREAM_DESTROYED', 'ECONNRESET'])

export function isClosedPipeError(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false
  }

  const code = (error as { code?: unknown }).code

  return typeof code === 'string' && PIPE_GONE_CODES.has(code)
}

/**
 * Attach a tolerant `'error'` handler to a stdio stream.
 *
 * A closed-pipe error is swallowed (the log line is lost, nothing else). Any
 * other stream error is re-surfaced on stderr *without* recursing back through
 * the guarded stream, so a real problem is still visible instead of vanishing.
 */
export function guardStdioStream(stream: StdioStreamLike | undefined | null): void {
  if (!stream || typeof stream.on !== 'function') {
    return
  }

  stream.on('error', (error: unknown) => {
    if (isClosedPipeError(error)) {
      return
    }

    // Best-effort report that cannot re-enter the guarded stream. Writing raw to
    // fd 2 can itself fail if stderr is the dead pipe, so it is wrapped.
    try {
      process.stderr.write(`[openamer] stdio stream error: ${String(error)}\n`)
    } catch {
      /* stderr is gone too — nothing left to report to */
    }
  })
}

/**
 * Install the stdio guards. Idempotent: calling twice does not stack handlers,
 * which matters because some entry paths run twice (dev reload, --no-sandbox
 * relaunch).
 */
let installed = false

export function installStdioGuards(): void {
  if (installed) {
    return
  }

  installed = true
  guardStdioStream(process.stdout as unknown as StdioStreamLike)
  guardStdioStream(process.stderr as unknown as StdioStreamLike)
}
