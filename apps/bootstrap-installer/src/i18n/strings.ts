/*
 * Installer copy — English and German.
 *
 * Why only two languages in the *installer*: the setup window is a few hundred
 * words of legal-ish chrome that must be right, not merely present. The product
 * it installs ships 186 locales (`apps/desktop/src/i18n/languages.ts`), and the
 * desktop asks for the language on its very first screen — so a person who does
 * not read English picks their language there, in its own script.
 *
 * Selection is automatic from the OS locale (`navigator.language`); there is no
 * picker here on purpose. A picker listing two languages next to a product that
 * speaks 186 would undersell it, and a picker listing 186 untranslated installer
 * strings would lie. Adding a language = one entry in `STRINGS`.
 */

export type Lang = 'de' | 'en'

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
  progress: {
    cancel: string
    done: string
    hideDetails: string
    lead: string
    leadUpdate: string
    lines: string
    liveOutput: string
    showDetails: string
    stepsComplete: (done: number, total: number) => string
    title: string
    titleUpdate: string
  }
  stepper: {
    done: string
    install: string
    update: string
    welcome: string
  }
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

const EN: Strings = {
  capabilities: [
    {
      body: 'OpenAmer plans a task, runs it with real tools — terminal, browser, files, code — and keeps what worked.',
      title: 'An agent that thinks along'
    },
    {
      body: 'Conversations, memory and models live on this machine. Nothing is uploaded unless you ask for it.',
      title: 'Your hardware, your data'
    },
    {
      body: '186 languages, each in the script you actually read. The first screen after setup asks which one.',
      title: 'Your language, properly'
    },
    {
      body: 'Skills are saved from the work itself, so everyday tasks get shorter the longer you use it.',
      title: 'Capability that grows'
    }
  ],
  failure: {
    help: [
      'Check that this machine can reach the internet.',
      'Run the setup again — finished steps are not repeated.',
      'If it fails twice, open the logs; the last lines name the step.'
    ],
    lead: 'No changes were rolled back silently — OpenAmer stops where it stopped, so a second run continues from there.',
    leadUpdate: 'OpenAmer is still on the previous version and keeps working. Nothing was half-replaced.',
    log: 'Log',
    openLogs: 'Open logs',
    retry: 'Try again',
    retryUpdate: 'Retry update',
    title: 'Setup didn’t finish',
    titleUpdate: 'Update didn’t finish'
  },
  progress: {
    cancel: 'Cancel',
    done: 'Ready',
    hideDetails: 'Hide details',
    lead: 'One-time setup: OpenAmer is downloading what it needs and configuring this machine. Later launches skip all of it.',
    leadUpdate: 'OpenAmer is replacing the previous version. Your sessions, memory and settings stay untouched.',
    lines: 'lines',
    liveOutput: 'Live output',
    showDetails: 'Show details',
    stepsComplete: (done, total) => `${done} of ${total} steps complete`,
    title: 'Setting up OpenAmer',
    titleUpdate: 'Updating OpenAmer'
  },
  stepper: {
    done: 'Ready',
    install: 'Install',
    update: 'Update',
    welcome: 'Welcome'
  },
  success: {
    cards: [
      {
        body: 'Open the app and describe what you want done. OpenAmer works in the background and reports back.',
        title: 'Start with a sentence'
      },
      {
        body: 'Settings → Display → Language. 186 locales, switchable at any time.',
        title: 'Pick your language'
      },
      {
        body: 'Recurring work becomes a skill — next time it takes one command.',
        title: 'Let it remember'
      }
    ],
    command: 'or start it later from a terminal:',
    cta: 'Launch OpenAmer',
    errorTitle: 'Couldn’t launch the desktop app',
    launching: 'Launching',
    lead: 'Everything is in place. OpenAmer is now yours — on this machine, in your language.',
    title: 'OpenAmer is ready'
  },
  welcome: {
    bullets: [
      'Runs locally — your conversations stay on this machine',
      '186 languages, including the script you read',
      'Everything can be changed later; nothing is permanent'
    ],
    cta: 'Install',
    ctaUpdate: 'Update now',
    kicker: 'One-time setup',
    lead: 'Your own agent. On your hardware. In your language.',
    leadUpdate: 'A newer OpenAmer is ready. This replaces the previous version and keeps every session and setting.',
    note: 'Takes a few minutes on a normal connection.',
    title: 'Welcome to OpenAmer',
    titleUpdate: 'Update OpenAmer'
  }
}

const DE: Strings = {
  capabilities: [
    {
      body: 'OpenAmer plant eine Aufgabe, führt sie mit echten Werkzeugen aus — Terminal, Browser, Dateien, Code — und behält, was funktioniert hat.',
      title: 'Ein Agent, der mitdenkt'
    },
    {
      body: 'Gespräche, Gedächtnis und Modelle bleiben auf diesem Rechner. Nichts wird hochgeladen, außer du willst es.',
      title: 'Deine Hardware, deine Daten'
    },
    {
      body: '186 Sprachen, jede in der Schrift, die du wirklich liest. Der erste Bildschirm nach der Einrichtung fragt danach.',
      title: 'Deine Sprache, richtig'
    },
    {
      body: 'Fähigkeiten entstehen aus der Arbeit selbst — wiederkehrende Aufgaben werden mit der Zeit kürzer.',
      title: 'Fähigkeiten, die wachsen'
    }
  ],
  failure: {
    help: [
      'Prüfe, ob dieser Rechner das Internet erreicht.',
      'Starte die Einrichtung erneut — fertige Schritte werden nicht wiederholt.',
      'Scheitert es zweimal, öffne die Logs; die letzten Zeilen nennen den Schritt.'
    ],
    lead: 'Es wurde nichts stillschweigend zurückgerollt — OpenAmer stoppt dort, wo es gestoppt hat, und ein zweiter Lauf macht von dort weiter.',
    leadUpdate: 'OpenAmer läuft weiter auf der vorherigen Version. Nichts wurde halb ersetzt.',
    log: 'Log',
    openLogs: 'Logs öffnen',
    retry: 'Erneut versuchen',
    retryUpdate: 'Update wiederholen',
    title: 'Einrichtung nicht abgeschlossen',
    titleUpdate: 'Update nicht abgeschlossen'
  },
  progress: {
    cancel: 'Abbrechen',
    done: 'Fertig',
    hideDetails: 'Details ausblenden',
    lead: 'Einmalige Einrichtung: OpenAmer lädt herunter, was es braucht, und richtet diesen Rechner ein. Spätere Starts überspringen das.',
    leadUpdate: 'OpenAmer ersetzt die vorherige Version. Sitzungen, Gedächtnis und Einstellungen bleiben unangetastet.',
    lines: 'Zeilen',
    liveOutput: 'Live-Ausgabe',
    showDetails: 'Details anzeigen',
    stepsComplete: (done, total) => `${done} von ${total} Schritten fertig`,
    title: 'OpenAmer wird eingerichtet',
    titleUpdate: 'OpenAmer wird aktualisiert'
  },
  stepper: {
    done: 'Fertig',
    install: 'Installation',
    update: 'Update',
    welcome: 'Willkommen'
  },
  success: {
    cards: [
      {
        body: 'Öffne die App und beschreibe, was erledigt werden soll. OpenAmer arbeitet im Hintergrund und meldet sich zurück.',
        title: 'Mit einem Satz anfangen'
      },
      {
        body: 'Einstellungen → Anzeige → Sprache. 186 Sprachen, jederzeit wechselbar.',
        title: 'Sprache wählen'
      },
      {
        body: 'Wiederkehrende Arbeit wird ein Skill — beim nächsten Mal ein Befehl.',
        title: 'Erinnern lassen'
      }
    ],
    command: 'oder später aus einem Terminal starten:',
    cta: 'OpenAmer starten',
    errorTitle: 'Desktop-App konnte nicht gestartet werden',
    launching: 'Startet',
    lead: 'Alles ist eingerichtet. OpenAmer gehört jetzt dir — auf diesem Rechner, in deiner Sprache.',
    title: 'OpenAmer ist bereit'
  },
  welcome: {
    bullets: [
      'Läuft lokal — deine Gespräche bleiben auf diesem Rechner',
      '186 Sprachen, auch die Schrift, die du liest',
      'Alles lässt sich später ändern; nichts ist festgeschrieben'
    ],
    cta: 'Installieren',
    ctaUpdate: 'Jetzt aktualisieren',
    kicker: 'Einmalige Einrichtung',
    lead: 'Dein eigener Agent. Auf deiner Hardware. In deiner Sprache.',
    leadUpdate: 'Eine neuere Version von OpenAmer ist bereit. Sie ersetzt die vorherige und behält jede Sitzung und Einstellung.',
    note: 'Dauert bei normaler Verbindung ein paar Minuten.',
    title: 'Willkommen bei OpenAmer',
    titleUpdate: 'OpenAmer aktualisieren'
  }
}

const STRINGS: Record<Lang, Strings> = { de: DE, en: EN }

/** OS language → installer language. Unknown locales get English. */
export function detectLang(): Lang {
  const candidates = [...(navigator.languages ?? []), navigator.language].filter(Boolean)

  for (const tag of candidates) {
    if (tag.toLowerCase().startsWith('de')) {
      return 'de'
    }
  }

  return 'en'
}

export function strings(lang: Lang = detectLang()): Strings {
  return STRINGS[lang]
}
