import { AlertCircle, ArrowRight } from 'lucide-react'
import { useState } from 'react'

import { HackeryButton } from '../components/hackery-button'
import { ReadyIllustration } from '../components/illustrations'
import { Stepper } from '../components/stepper'
import { useStrings } from '../i18n'
import { launchOpenAmerDesktop } from '../store'

/*
 * Success — step 3 of 3.
 *
 * This is the screen the whole installer exists for, so it gets the one
 * celebratory drawing in the product (the check inside a burst) and then
 * immediately turns useful: three cards that say what to do in the first five
 * minutes, not a paragraph about what was installed.
 *
 * Launching the desktop can fail (e.g. the desktop stage was skipped and
 * OpenAmer.exe does not exist). The rejection is surfaced inline rather than
 * swallowed, so the button never looks broken.
 */
export default function Success() {
  const [error, setError] = useState<string | null>(null)
  const [launching, setLaunching] = useState(false)
  const s = useStrings()

  async function handleLaunch() {
    setError(null)
    setLaunching(true)

    try {
      await launchOpenAmerDesktop()
      // On success the installer exits — control never returns here.
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
      setLaunching(false)
    }
  }

  return (
    <div className="openamer-fade-in flex h-full flex-col">
      <div className="flex min-h-0 flex-1">
        <div className="flex w-[45%] min-w-0 flex-col justify-center px-9 py-8">
          <div className="size-[132px] text-primary">
            <ReadyIllustration />
          </div>

          <h1 className="mt-3 max-w-[16ch] text-[28px] leading-[1.12] font-semibold tracking-[-0.02em] text-foreground">
            {s.success.title}
          </h1>
          <p className="mt-2.5 max-w-[38ch] text-[13.5px] leading-relaxed text-muted-foreground">{s.success.lead}</p>

          <div className="mt-6 flex items-center gap-3">
            <HackeryButton
              disabled={launching}
              label={
                <span className="inline-flex items-center gap-2">
                  {launching ? s.success.launching : s.success.cta}
                  <ArrowRight className="size-3 text-primary/70 rtl:-scale-x-100" />
                </span>
              }
              loading={launching}
              onClick={() => void handleLaunch()}
            />
          </div>

          <p className="mt-4 text-[11px] text-foreground/40">
            {s.success.command}{' '}
            <code className="rounded bg-foreground/[0.06] px-1.5 py-0.5 font-mono text-[10.5px] text-foreground/70">
              openamer desktop
            </code>
          </p>

          {error && (
            <div className="mt-5 flex max-w-md items-start gap-2 text-[12px]" role="alert">
              <AlertCircle className="mt-0.5 shrink-0 text-destructive" size={14} />
              <div className="min-w-0">
                <div className="font-medium text-destructive">{s.success.errorTitle}</div>
                <div className="mt-0.5 text-muted-foreground">{error}</div>
              </div>
            </div>
          )}
        </div>

        <div className="flex min-w-0 flex-1 flex-col justify-center border-s border-foreground/10 px-7 py-8">
          <span className="text-[10.5px] font-semibold tracking-[0.2em] text-foreground/35 uppercase">
            {s.stepper.done}
          </span>
          <ul className="mt-3 space-y-2.5">
            {s.success.cards.map((card, i) => (
              <li className="installer-card rounded-xl border border-foreground/10 px-3.5 py-3" key={card.title}>
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-[10px] tabular-nums text-primary/60">{String(i + 1).padStart(2, '0')}</span>
                  <h3 className="text-[13px] font-medium tracking-tight text-foreground">{card.title}</h3>
                </div>
                <p className="mt-1 ps-[22px] text-[11.5px] leading-relaxed text-muted-foreground">{card.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="flex shrink-0 items-center justify-between border-t border-foreground/10 px-9 py-3">
        <Stepper
          current={3}
          steps={[s.stepper.language, s.stepper.welcome, s.stepper.install, s.stepper.done]}
        />
        <span className="font-mono text-[10px] tracking-[0.18em] text-foreground/25 uppercase">openamer.com</span>
      </div>
    </div>
  )
}
