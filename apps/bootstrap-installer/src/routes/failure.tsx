import { useStore } from '@nanostores/react'
import { FileText, RefreshCw } from 'lucide-react'

import { Button } from '../components/button'
import { LocalComputeIllustration } from '../components/illustrations'
import { Stepper } from '../components/stepper'
import { detectLang, strings } from '../i18n/strings'
import { $logPath, $mode, type BootstrapStateModel, openLogDir, startInstall, startUpdate } from '../store'

interface FailureProps {
  bootstrap: BootstrapStateModel
}

/*
 * Failure — the screen nobody wants, so it gets the calmest treatment in the
 * set. No red hero type, no alarm icon repeated three times: one short sentence
 * of what happened, the technical detail in muted type, and three things the
 * person can actually do. The drawing is the same compute die as the welcome
 * screen on purpose — nothing is broken, the run stopped.
 */
export default function Failure({ bootstrap }: FailureProps) {
  const logPath = useStore($logPath)
  const mode = useStore($mode)
  const isUpdate = mode === 'update'
  const s = strings(detectLang())

  return (
    <div className="openamer-fade-in flex h-full flex-col">
      <div className="flex min-h-0 flex-1">
        <div className="flex w-[45%] min-w-0 flex-col justify-center px-9 py-8">
          <div className="size-[124px] text-destructive/80">
            <LocalComputeIllustration label="Setup stopped" tight />
          </div>

          <h1 className="mt-3 max-w-[20ch] text-[26px] leading-[1.14] font-semibold tracking-[-0.02em] text-foreground">
            {isUpdate ? s.failure.titleUpdate : s.failure.title}
          </h1>

          <p className="mt-2.5 max-w-[40ch] text-[13px] leading-relaxed text-muted-foreground">
            {isUpdate ? s.failure.leadUpdate : s.failure.lead}
          </p>

          {bootstrap.error && (
            <pre className="mt-4 max-h-28 max-w-md overflow-auto rounded-lg border border-foreground/10 bg-foreground/[0.03] px-3 py-2 font-mono text-[10.5px] leading-relaxed whitespace-pre-wrap text-foreground/60">
              {bootstrap.error}
            </pre>
          )}

          <div className="mt-5 flex items-center gap-3">
            <Button className="gap-1.5" onClick={() => void (isUpdate ? startUpdate() : startInstall())}>
              <RefreshCw />
              {isUpdate ? s.failure.retryUpdate : s.failure.retry}
            </Button>
            <Button className="gap-1.5" onClick={() => void openLogDir()} variant="text">
              <FileText />
              {s.failure.openLogs}
            </Button>
          </div>

          {logPath && (
            <p className="mt-3 max-w-md truncate text-[10.5px] text-foreground/35">
              {s.failure.log}: <code className="font-mono">{logPath}</code>
            </p>
          )}
        </div>

        <div className="flex min-w-0 flex-1 flex-col justify-center border-l border-foreground/10 px-7 py-8">
          <ul className="space-y-2.5">
            {s.failure.help.map((line, i) => (
              <li className="flex items-start gap-2.5 text-[12px] leading-relaxed text-muted-foreground" key={line}>
                <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border border-foreground/15 font-mono text-[9px] text-foreground/45">
                  {i + 1}
                </span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="flex shrink-0 items-center justify-between border-t border-foreground/10 px-9 py-3">
        <Stepper current={1} labels={s.stepper} update={isUpdate} />
        <span className="font-mono text-[10px] tracking-[0.18em] text-foreground/25 uppercase">openamer.dev</span>
      </div>
    </div>
  )
}
