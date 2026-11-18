import { useStore } from '@nanostores/react'
import { ArrowRight, Languages, Lock, Sparkles } from 'lucide-react'

import { BrandMark } from '../components/brand-mark'
import { CapabilityStage } from '../components/capability-stage'
import { HackeryButton } from '../components/hackery-button'
import { Stepper } from '../components/stepper'
import { useStrings } from '../i18n'
import { $mode, startInstall } from '../store'

/*
 * Welcome — step 1 of 3.
 *
 * Left column is the decision: what this is, what it will do to the machine, and
 * one button. Right column is the reason to be glad about it: a rotating
 * illustration of a property the product actually has. The claim and the picture
 * deliberately do not say the same sentence — the left side answers "is this
 * safe and quick", the right side answers "what do I get".
 *
 * Update mode reuses this screen with different copy: same single decision, but
 * the promise becomes "nothing of yours is touched".
 */
const BULLET_ICONS = [Lock, Languages, Sparkles]

export default function Welcome() {
  const mode = useStore($mode)
  const s = useStrings()
  const isUpdate = mode === 'update'

  return (
    <div className="openamer-fade-in flex h-full flex-col">
      <div className="flex min-h-0 flex-1">
        {/* Decision column */}
        <div className="mx-auto flex w-full max-w-[620px] min-w-0 flex-[1.05] flex-col justify-center px-9 py-8 min-[1000px]:mx-0 min-[1000px]:max-w-none">
          <div className="mb-5 flex items-center gap-3">
            <BrandMark className="size-10 rounded-md" />
            <div className="min-w-0">
              <div className="text-[11px] font-semibold tracking-[0.22em] text-foreground/55 uppercase">
                {s.welcome.kicker}
              </div>
              <div className="text-[11px] tracking-tight text-foreground/35">OpenAmer Setup</div>
            </div>
          </div>

          <h1 className="max-w-[19ch] text-[30px] leading-[1.1] font-semibold tracking-[-0.02em] text-foreground">
            {isUpdate ? s.welcome.titleUpdate : s.welcome.title}
          </h1>

          <p className="mt-3 max-w-[42ch] text-[15px] leading-relaxed font-medium text-foreground/80">
            {isUpdate ? s.welcome.leadUpdate : s.welcome.lead}
          </p>

          {!isUpdate && (
            <ul className="mt-5 space-y-2.5">
              {s.welcome.bullets.map((bullet, i) => {
                const Icon = BULLET_ICONS[i % BULLET_ICONS.length] ?? Lock

                return (
                  <li className="flex items-start gap-2.5 text-[12.5px] leading-relaxed text-muted-foreground" key={bullet}>
                    <Icon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-primary/70" />
                    <span>{bullet}</span>
                  </li>
                )
              })}
            </ul>
          )}

          <div className="mt-7 flex items-center gap-3">
            <HackeryButton
              label={
                <span className="inline-flex items-center gap-2">
                  {isUpdate ? s.welcome.ctaUpdate : s.welcome.cta}
                  <ArrowRight className="size-3 text-primary/70" />
                </span>
              }
              onClick={() => void startInstall()}
            />
          </div>

          <p className="mt-3 text-[11px] text-foreground/35">{s.welcome.note}</p>
        </div>

        {/* Evidence column. Below 860px the drawing is dropped rather than
            squeezed: a cramped illustration beside cramped text is worse than a
            clean single column, and scaled displays can leave the webview
            narrower than the window config suggests. */}
        <div className="hidden min-w-0 flex-1 border-l border-foreground/10 px-7 py-7 min-[860px]:flex">
          <CapabilityStage capabilities={s.capabilities} />
        </div>
      </div>

      <div className="flex shrink-0 items-center justify-between border-t border-foreground/10 px-9 py-3">
        <Stepper
          current={isUpdate ? 0 : 1}
          steps={
            isUpdate
              ? [s.stepper.update, s.stepper.install, s.stepper.done]
              : [s.stepper.language, s.stepper.welcome, s.stepper.install, s.stepper.done]
          }
        />
        <span className="font-mono text-[10px] tracking-[0.18em] text-foreground/25 uppercase">openamer.dev</span>
      </div>
    </div>
  )
}
