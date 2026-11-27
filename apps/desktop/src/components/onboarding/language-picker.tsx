// DesktopLanguagePickerOverlay — the first thing a new user sees after install.
//
// OpenAmer has no "default language everyone understands": English is just
// another locale. So the very first screen asks which language you read, in
// that language's own script (endonyms, never romanized), and only then does
// the provider onboarding appear — already in the chosen language. Nobody has
// to understand English to find the language switch.
//
// Persistence: the locale itself lives in `config.display.language` (written by
// `setLocale` from the i18n provider). A renderer-local flag records that the
// question was answered — including an explicit "Skip", or a pick of English —
// so the picker never re-nags on later launches.
import { useCallback, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { LOCALE_OPTIONS, useI18n } from '@/i18n'
import type { Locale } from '@/i18n/types'
import { normalize } from '@/lib/text'

const CHOSEN_KEY = 'openamer-language-chosen-v1'

function readChosen(): boolean {
  if (typeof window === 'undefined') {
    return false
  }

  try {
    return window.localStorage.getItem(CHOSEN_KEY) === '1'
  } catch {
    return false
  }
}

function writeChosen() {
  if (typeof window === 'undefined') {
    return
  }

  try {
    window.localStorage.setItem(CHOSEN_KEY, '1')
  } catch {
    // localStorage unavailable — the config value still persists the choice.
  }
}

interface DesktopLanguagePickerOverlayProps {
  enabled: boolean
  onCompleted: () => void
}

export function DesktopLanguagePickerOverlay({ enabled, onCompleted }: DesktopLanguagePickerOverlayProps) {
  const { configuredLanguage, t, isSavingLocale, setLocale } = useI18n()
  const [chosen, setChosen] = useState(readChosen)
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Alphabetical by English name so the order is predictable; the endonym is
  // what the eye actually lands on in the list.
  const options = useMemo(() => {
    const sorted = [...LOCALE_OPTIONS].sort((a, b) => a.englishName.localeCompare(b.englishName))
    const needle = normalize(query.trim())

    if (!needle) {
      return sorted
    }

    return sorted.filter(option => {
      return (
        normalize(option.name).includes(needle) ||
        normalize(option.englishName).includes(needle) ||
        option.id.startsWith(needle)
      )
    })
  }, [query])

  const finish = useCallback(() => {
    writeChosen()
    setChosen(true)
    onCompleted()
  }, [onCompleted])

  const pick = useCallback(
    async (code: string) => {
      setError(null)

      try {
        await setLocale(code as Locale)
        finish()
      } catch (err) {
        setError(err instanceof Error ? err.message : t.language.saveError)
      }
    },
    [finish, setLocale, t.language.saveError]
  )

  // The setup window asks this question on its FIRST screen and writes the answer
  // into `display.language`. A config value that exists therefore means the
  // question is already answered — whether the installer set it or the person
  // changed it later in Settings. Derived, not stored: the config arrives
  // asynchronously, so a value captured at mount would miss it.
  if (!enabled || chosen || Boolean(configuredLanguage)) {
    return null
  }

  return (
    <div className="fixed inset-0 z-1400 flex items-center justify-center bg-(--ui-chat-surface-background) p-6">
      <div className="flex max-h-[85dvh] w-full max-w-[34rem] flex-col overflow-hidden rounded-xl border border-(--stroke-openamer) bg-(--ui-chat-bubble-background) shadow-openamer">
        <div className="px-5 pt-5 pb-1">
          <h2 className="text-[0.9375rem] font-semibold tracking-tight">{t.language.label}</h2>
          <p className="mt-1 text-[0.8125rem] leading-5 text-(--ui-text-tertiary)">{t.language.description}</p>
        </div>

        <div className="px-5 pt-3">
          <Input
            autoFocus
            onChange={event => setQuery(event.target.value)}
            placeholder={t.language.searchPlaceholder}
            value={query}
          />
        </div>

        {error ? <p className="px-5 pt-2 text-xs text-destructive">{error}</p> : null}

        <div className="mt-2 min-h-0 flex-1 overflow-y-auto px-3 pb-2">
          {options.length === 0 ? (
            <p className="px-2 py-6 text-center text-[0.8125rem] text-(--ui-text-tertiary)">{t.language.noResults}</p>
          ) : (
            <ul className="grid gap-0.5">
              {options.map(option => (
                <li key={option.id}>
                  <button
                    className="flex w-full items-baseline justify-between gap-3 rounded-lg px-3 py-2 text-start transition-colors hover:bg-(--chrome-action-hover) disabled:opacity-50"
                    disabled={isSavingLocale}
                    onClick={() => void pick(option.configValue)}
                    type="button"
                  >
                    <span className="text-[0.875rem] font-medium" lang={option.id}>
                      {option.name}
                    </span>
                    <span className="shrink-0 text-[0.6875rem] text-(--ui-text-tertiary)">{option.englishName}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex items-center justify-between gap-2 border-t border-(--ui-stroke-tertiary) px-5 py-3">
          <span className="text-[0.6875rem] text-(--ui-text-tertiary)">{isSavingLocale ? t.language.saving : ''}</span>
          <Button disabled={isSavingLocale} onClick={finish} size="sm" type="button" variant="ghost">
            {t.common.skip}
          </Button>
        </div>
      </div>
    </div>
  )
}
