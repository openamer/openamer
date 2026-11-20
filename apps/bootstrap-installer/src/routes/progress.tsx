import { useStore } from '@nanostores/react'
import clsx from 'clsx'
import { Check, ChevronRight, FileText, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { BrandMark } from '../components/brand-mark'
import { Button } from '../components/button'
import { ProgressRing } from '../components/illustrations'
import { Loader } from '../components/loader'
import { Stepper } from '../components/stepper'
import { fmt, useStrings } from '../i18n'
import {
  $mode,
  $progress,
  type BootstrapStateModel,
  cancelInstall,
  type StageState
} from '../store'

interface ProgressProps {
  bootstrap: BootstrapStateModel
}

/*
 * Progress — step 2 of 3.
 *
 * Layout change from the previous screen: the number, the ring and the step list
 * are one object on the left (where the eye goes for "how long"), the log is a
 * panel that slides in from the right only when asked for. The stage list keeps
 * its semantics — only the running step is opaque, a running step shows a live
 * elapsed clock, and terminal markers stay neutral (a muted check, no
 * celebratory green: finishing a step is not the finish).
 */
export default function ProgressScreen({ bootstrap }: ProgressProps) {
  const progress = useStore($progress)
  const mode = useStore($mode)
  const [showLogs, setShowLogs] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const logEndRef = useRef<HTMLDivElement>(null)

  const s = useStrings()

  useEffect(() => {
    if (showLogs && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [bootstrap.logs.length, showLogs])

  // Tick once a second while the run is in flight so the active step shows a
  // live elapsed timer — a long single step (e.g. the dependency download)
  // reads as working, not frozen. Stops when nothing is running.
  useEffect(() => {
    if (bootstrap.status !== 'running') {
      return
    }

    const id = window.setInterval(() => setNow(Date.now()), 1000)

    return () => window.clearInterval(id)
  }, [bootstrap.status])

  const isUpdate = mode === 'update'
  const pct = Math.round(progress.fraction * 100)
  const running = bootstrap.status === 'running'

  // The headline is the biggest text on the screen, so it must be in the chosen
  // language: the manifest ships English stage titles, the catalogue carries the
  // translation. Without this the update window read "Downloading the latest
  // version" in the middle of an otherwise German screen.
  const currentStageName = bootstrap.currentStage

  const currentTitle =
    currentStageName != null
      ? (s.stages[currentStageName] ?? bootstrap.stages[currentStageName]?.info.title ?? null)
      : null

  return (
    <div className="openamer-fade-in flex h-full flex-col">
      <div className={clsx('flex min-h-0 flex-1', !showLogs && 'justify-center')}>
        {/* Left: the number, then the steps. With the log closed this column
            takes the whole window instead of leaving a dead grey panel. */}
        <div
          className={clsx(
            'flex min-w-0 flex-col px-7 py-6',
            showLogs
              ? 'w-[46%] border-e border-foreground/10'
              : // Closed log: the block sits in the optical middle instead of
                // hanging off the top edge with half the window empty below.
                'w-full max-w-[640px] justify-center'
          )}
        >
          <div className="flex items-center gap-2.5">
            <BrandMark className="size-7 rounded" />
            <span className="text-[10.5px] font-semibold tracking-[0.2em] text-foreground/45 uppercase">
              {isUpdate ? s.progress.titleUpdate : s.progress.title}
            </span>
          </div>

          <div className="mt-4 flex items-center gap-4">
            <div className="relative size-[104px] shrink-0 text-primary">
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -inset-3 rounded-full bg-primary/[0.07] blur-xl"
              />
              <ProgressRing pct={pct} />
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-[21px] leading-none font-semibold tabular-nums text-foreground">{pct}%</span>
                {bootstrap.status === 'completed' && (
                  <span className="mt-1 text-[9px] tracking-[0.14em] text-foreground/45 uppercase">
                    {s.progress.done}
                  </span>
                )}
              </div>
            </div>
            <div className="min-w-0">
              <p className={clsx('truncate text-[13px] font-medium text-foreground', running && 'shimmer')}>
                {currentTitle ?? (isUpdate ? s.progress.titleUpdate : s.progress.title)}
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground">
                {fmt(s.progress.stepsComplete, { done: progress.done, total: progress.total })}
              </p>
            </div>
          </div>

          <p className="mt-4 text-[11.5px] leading-relaxed text-muted-foreground/80">
            {isUpdate ? s.progress.leadUpdate : s.progress.lead}
          </p>

          <ol
            className={clsx(
              'mt-5 ms-1.5 space-y-1 border-s border-foreground/10 ps-4 pe-1',
              // Only scroll when the log is open and space is actually tight;
              // otherwise the rail would stretch past the last step.
              showLogs && 'min-h-0 flex-1 overflow-y-auto'
            )}
          >
            {bootstrap.stageOrder.map((name) => {
              const rec = bootstrap.stages[name]

              if (!rec) {
                return null
              }

              const meta =
                rec.state === 'running' && rec.startedAt != null
                  ? formatElapsed(now - rec.startedAt)
                  : rec.durationMs != null && rec.state !== 'failed'
                    ? formatDuration(rec.durationMs)
                    : null

              return (
                <li
                  className={clsx(
                    'relative flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[12.5px]',
                    rec.state === 'running'
                      ? 'bg-primary/[0.07] font-medium text-foreground'
                      : 'text-muted-foreground',
                    rec.state == null ? 'opacity-55' : ''
                  )}
                  key={name}
                >
                  <span
                    aria-hidden="true"
                    className={clsx(
                      'absolute -start-[21px] top-1/2 size-1.5 -translate-y-1/2 rounded-full',
                      rec.state === 'running'
                        ? 'bg-primary ring-2 ring-primary/25'
                        : rec.state === 'succeeded'
                          ? 'bg-primary/60'
                          : rec.state === 'failed'
                            ? 'bg-destructive'
                            : 'bg-foreground/20'
                    )}
                  />
                  {rec.state === 'running' && <Loader className="-ms-1.5 size-5 shrink-0" />}
                  <span className="flex-1 truncate">{s.stages[name] ?? rec.info.title}</span>
                  {meta && <span className="text-[10.5px] tabular-nums text-muted-foreground/60">{meta}</span>}
                  <StateIcon state={rec.state ?? null} />
                </li>
              )
            })}
          </ol>
        </div>

        {/* Right: live output, only when it is actually open */}
        <div className={clsx('flex min-w-0 flex-1 flex-col px-6 py-6', !showLogs && 'hidden')}>
          <div className="flex items-center justify-between">
            <span className="text-[10.5px] font-semibold tracking-[0.18em] text-foreground/40 uppercase">
              {s.progress.liveOutput}
            </span>
            <span className="text-[10.5px] tabular-nums text-foreground/35">
              {bootstrap.logs.length} {s.progress.lines}
            </span>
          </div>

          <div
            className={clsx(
              'installer-log mt-2 min-h-0 flex-1 overflow-y-auto rounded-lg border border-foreground/10 bg-foreground/[0.03] px-3 py-2 font-mono text-[10.5px] leading-relaxed'
            )}
          >
            {bootstrap.logs.length === 0 ? (
              <div className="text-foreground/25">—</div>
            ) : (
              bootstrap.logs.map((entry, idx) => (
                <div
                  className={clsx(
                    'whitespace-pre-wrap',
                    entry.stream === 'stderr' ? 'text-foreground/40' : 'text-foreground/70'
                  )}
                  key={idx}
                >
                  {entry.line}
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>

      <div className="flex shrink-0 items-center justify-between border-t border-foreground/10 px-7 py-2.5">
        <Stepper
          current={isUpdate ? 1 : 2}
          steps={
            isUpdate
              ? [s.stepper.update, s.stepper.install, s.stepper.done]
              : [s.stepper.language, s.stepper.welcome, s.stepper.install, s.stepper.done]
          }
        />

        <div className="flex items-center gap-4">
          <button
            className="inline-flex cursor-pointer items-center gap-1.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
            onClick={() => setShowLogs(v => !v)}
            type="button"
          >
            <FileText size={13} />
            {showLogs ? s.progress.hideDetails : s.progress.showDetails}
            <ChevronRight className={clsx('transition-transform rtl:-scale-x-100', showLogs && 'rotate-90')} size={11} />
          </button>

          {running && (
            <Button onClick={() => void cancelInstall()} size="sm" variant="outline">
              {s.progress.cancel}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

// Terminal-state markers, neutral by design: a muted check for done/skipped
// (no celebratory green), a destructive cross for failure. Running renders its
// spinner on the left; pending stays icon-less.
function StateIcon({ state }: { state: StageState | null }) {
  if (state === 'succeeded') {
    return <Check className="shrink-0 text-muted-foreground" size={13} />
  }

  if (state === 'skipped') {
    return <Check className="shrink-0 text-muted-foreground/50" size={13} />
  }

  if (state === 'failed') {
    return <X className="shrink-0 text-destructive" size={13} />
  }

  return null
}

function formatDuration(ms: number): string {
  if (ms < 1000) {return `${ms}ms`}

  if (ms < 60000) {return `${(ms / 1000).toFixed(1)}s`}
  const m = Math.floor(ms / 60000)
  const s = Math.round((ms % 60000) / 1000)

  return `${m}m ${s}s`
}

// Live elapsed for a running stage: bare seconds under a minute, then m:ss.
function formatElapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))

  if (s < 60) {return `${s}s`}
  const m = Math.floor(s / 60)

  return `${m}:${String(s - m * 60).padStart(2, '0')}`
}
