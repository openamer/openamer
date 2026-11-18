import { useStore } from '@nanostores/react'
import clsx from 'clsx'
import { ArrowRight, Check, Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import { BrandMark } from '../components/brand-mark'
import { HackeryButton } from '../components/hackery-button'
import { Stepper } from '../components/stepper'
import { $lang, LANGUAGE_ENTRIES, setLang, useStrings } from '../i18n'
import { $route } from '../store'

/*
 * Language — the first screen, the way an OS installer starts.
 *
 * Why this exists as its own step instead of a dropdown buried in settings: the
 * person installing has not seen the product yet, so every sentence after this
 * one is the product's first impression. Asking in a language they read is the
 * difference between "software for people like me" and "software I have to
 * translate in my head".
 *
 * The list is built from the catalogues that actually shipped (see
 * `LANGUAGE_ENTRIES`), so nothing here can promise a translation that does not
 * exist. The OS language is preselected when the installer speaks it — Ubuntu's
 * behaviour — and typing filters by endonym OR English name, because someone who
 * reads "Deutsch" may still search for "German".
 */
function fold(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

export default function Language() {
  const s = useStrings()
  const active = useStore($lang)
  const [query, setQuery] = useState('')

  const entries = useMemo(() => {
    const needle = fold(query.trim())

    if (!needle) {
      return LANGUAGE_ENTRIES
    }

    return LANGUAGE_ENTRIES.filter(
      entry => fold(entry.endonym).includes(needle) || fold(entry.englishName).includes(needle) || fold(entry.code).includes(needle)
    )
  }, [query])

  const steps = [s.stepper.language, s.stepper.welcome, s.stepper.install, s.stepper.done]

  return (
    <div className="openamer-fade-in flex h-full flex-col">
      <div className="flex min-h-0 flex-1 flex-col px-9 pt-8">
        <div className="flex items-center gap-3">
          <BrandMark className="size-10 rounded-md" />
          <div className="min-w-0">
            <div className="text-[11px] font-semibold tracking-[0.22em] text-foreground/55 uppercase">
              {s.welcome.kicker}
            </div>
            <div className="text-[11px] tracking-tight text-foreground/35">OpenAmer Setup</div>
          </div>
        </div>

        <h1 className="mt-6 max-w-[24ch] text-[27px] leading-[1.15] font-semibold tracking-[-0.02em] text-foreground">
          {s.language.title}
        </h1>
        <p className="mt-2 max-w-[62ch] text-[13px] leading-relaxed text-muted-foreground">{s.language.lead}</p>

        <label className="relative mt-5 block max-w-[420px]">
          <Search aria-hidden="true" className="absolute top-1/2 start-2.5 size-3.5 -translate-y-1/2 text-foreground/35" />
          <input
            aria-label={s.language.search}
            autoFocus
            className="w-full rounded-md border border-foreground/15 bg-foreground/[0.03] py-1.5 pe-3 ps-8 text-[12.5px] text-foreground outline-none placeholder:text-foreground/30 focus-visible:border-primary/60"
            onChange={event => setQuery(event.target.value)}
            placeholder={s.language.search}
            spellCheck={false}
            type="search"
            value={query}
          />
        </label>

        <div className="mt-3 min-h-0 flex-1 overflow-y-auto pe-1 pb-3">
          <ul className="grid grid-cols-2 gap-1 min-[1000px]:grid-cols-3">
            {entries.map(entry => {
              const selected = entry.code === active

              return (
                <li key={entry.code}>
                  <button
                    aria-pressed={selected}
                    className={clsx(
                      'flex w-full cursor-pointer items-center gap-2 rounded-md border px-2 py-1.5 text-start transition-colors',
                      selected
                        ? 'border-primary/70 bg-primary/[0.08]'
                        : 'border-foreground/10 hover:border-foreground/25 hover:bg-foreground/[0.04]'
                    )}
                    lang={entry.code}
                    onClick={() => void setLang(entry.code)}
                    type="button"
                  >
                    <span className="min-w-0 flex-1">
                      <span
                        className={clsx(
                          'block truncate text-[12px] leading-tight',
                          selected ? 'font-medium text-foreground' : 'text-foreground/85'
                        )}
                      >
                        {entry.endonym}
                      </span>
                      <span className="block truncate text-[10px] leading-tight text-foreground/35">
                        {entry.englishName}
                      </span>
                    </span>
                    {selected && <Check className="size-3.5 shrink-0 text-primary" />}
                  </button>
                </li>
              )
            })}
          </ul>

          {entries.length === 0 && <p className="py-6 text-center text-[12px] text-foreground/40">—</p>}
        </div>
      </div>

      <div className="flex shrink-0 items-center justify-between border-t border-foreground/10 px-9 py-3">
        <Stepper current={0} steps={steps} />

        <div className="flex items-center gap-3">
          <HackeryButton
            label={
              <span className="inline-flex items-center gap-2">
                {s.language.continue}
                <ArrowRight className="size-3 text-primary/70 rtl:-scale-x-100" />
              </span>
            }
            onClick={() => $route.set('welcome')}
          />
        </div>
      </div>
    </div>
  )
}
