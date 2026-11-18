/*
 * Installer i18n — catalogues as data, not code.
 *
 * Structure: every shipped language is a JSON file under `catalogs/`, mirroring
 * the `Strings` shape below. They are discovered at build time, so adding a
 * language is adding a file — no import list to keep in sync.
 *
 * The installer asks for the language on its FIRST screen and then runs the
 * whole setup in that language (the Ubuntu pattern). That only works if the copy
 * is data: a language that exists in `language-names.json` but has no catalogue
 * would be offered and then fall back to English mid-flow, which is worse than
 * not offering it. So the picker is built from the catalogues that exist.
 */
export type Lang = string

/** Text with `{name}` placeholders. Kept as data so it can be translated. */
export type Template = string

export interface Capability {
  body: string
  title: string
}

export interface Strings {
  capabilities: Capability[]
  failure: {
    help: string[]
    lead: string
    leadUpdate: string
    log: string
    openLogs: string
    retry: string
    retryUpdate: string
    title: string
    titleUpdate: string
  }
  language: {
    continue: string
    lead: string
    search: string
    title: string
  }
  progress: {
    cancel: string
    done: string
    hideDetails: string
    lead: string
    leadUpdate: string
    lines: string
    liveOutput: string
    showDetails: string
    stepsComplete: Template
    title: string
    titleUpdate: string
  }
  stepper: {
    done: string
    install: string
    language: string
    update: string
    welcome: string
  }
  /**
   * Stage titles by install-script stage name. The manifest ships English titles
   * from `scripts/install.ps1`; the setup window prefers these and falls back to
   * the manifest when a stage is unknown (a new stage must not render blank).
   */
  stages: Record<string, string>
  success: {
    cards: Capability[]
    command: string
    cta: string
    errorTitle: string
    launching: string
    lead: string
    title: string
  }
  welcome: {
    bullets: string[]
    cta: string
    ctaUpdate: string
    kicker: string
    lead: string
    leadUpdate: string
    note: string
    title: string
    titleUpdate: string
  }
}

/** Fallback: the source language. Every catalogue is checked against its keys. */
export const FALLBACK: Lang = 'en'

const MODULES = import.meta.glob<{ default: Strings }>('./catalogs/*.json', { eager: true })

/** code -> catalogue, discovered from the bundled JSON files. */
export const CATALOGS: Record<Lang, Strings> = Object.fromEntries(
  Object.entries(MODULES).map(([path, mod]) => [path.slice(path.lastIndexOf('/') + 1, -5), mod.default])
)

export const LANGUAGES: Lang[] = Object.keys(CATALOGS).sort()
