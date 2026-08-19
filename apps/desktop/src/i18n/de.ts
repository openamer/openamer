import { defineLocale } from './define-locale'

export const de = defineLocale({
  common: {
    apply: 'Übernehmen',
    back: 'Zurück',
    save: 'Speichern',
    saving: 'Speichern…',
    cancel: 'Abbrechen',
    change: 'Ändern',
    choose: 'Auswählen',
    clear: 'Löschen',
    close: 'Schließen',
    collapse: 'Einklappen',
    confirm: 'Bestätigen',
    connect: 'Verbinden',
    connecting: 'Verbinde',
    continue: 'Weiter',
    copied: 'Kopiert',
    copy: 'Kopieren',
    copyFailed: 'Kopieren fehlgeschlagen',
    delete: 'Löschen',
    docs: 'Dokumentation',
    done: 'Fertig',
    error: 'Fehler',
    expand: 'Ausklappen',
    failed: 'Fehlgeschlagen',
    formatJson: 'JSON formatieren',
    free: 'Kostenlos',
    loading: 'Lädt…',
    notSet: 'Nicht gesetzt',
    refresh: 'Aktualisieren',
    remove: 'Entfernen',
    replace: 'Ersetzen',
    retry: 'Wiederholen',
    run: 'Ausführen',
    send: 'Senden',
    set: 'Setzen',
    skip: 'Überspringen',
    update: 'Aktualisieren',
    tryHint: (term: string) => `Versuche „${term}”`,
    on: 'An',
    off: 'Aus'
  },

  fileMenu: {
    revealExplorer: 'Im Explorer anzeigen',
    revealFileManager: 'Enthaltenden Ordner öffnen',
    revealInSidebar: 'In Dateibaum anzeigen',
    copyPath: 'Pfad kopieren',
    copyRelativePath: 'Relativen Pfad kopieren',
    rename: 'Umbenennen…',
    renameTitle: 'Umbenennen',
    renameLabel: 'Neuer Name',
    deleteTitle: (name: string) => `${name} löschen?`,
    deleteBody: 'Die Datei wird in den Papierkorb verschoben — du kannst sie von dort wiederherstellen.',
    pathCopied: 'Pfad kopiert'
  },

  boot: {
    ready: 'OpenAmer Desktop ist bereit',
    desktopBootFailedWithMessage: (message: string) => `Desktop-Start fehlgeschlagen: ${message}`,
    steps: {
      connectingGateway: 'Verbinde Gateway',
      loadingSettings: 'Lade Einstellungen',
      loadingSessions: 'Lade letzte Sessions',
      startingDesktopConnection: 'Starte Desktop-Verbindung',
      startingOpenAmerDesktop: 'Starte OpenAmer Desktop…'
    },
    errors: {
      backgroundExited: 'OpenAmer Hintergrundprozess wurde beendet.',
      backgroundExitedDuringStartup: 'OpenAmer Hintergrundprozess wurde während des Starts beendet.',
      backendStopped: 'Backend gestoppt',
      desktopBootFailed: 'Desktop-Start fehlgeschlagen',
      gatewayConnectionLost: 'Verbindung zum Gateway verloren',
      gatewaySignInRequired: 'Gateway-Anmeldung erforderlich',
      ipcBridgeUnavailable: 'Desktop IPC-Brücke nicht verfügbar.'
    },
    failure: {
      title: 'OpenAmer konnte nicht starten',
      description:
        'Das Hintergrund-Gateway wurde nicht gestartet. Versuche einen der folgenden Schritte. Deine Chats und Einstellungen bleiben erhalten.',
      retry: 'Wiederholen',
      repairInstall: 'Installation reparieren',
      useLocalGateway: 'Lokales Gateway verwenden',
      gatewaySettings: 'Gateway-Einstellungen',
      back: 'Zurück',
      openLogs: 'Logs öffnen',
      repairHint: 'Die Reparatur führt das Installationsprogramm erneut aus und kann einige Minuten dauern.',
      signOutAndSignIn: 'Abmelden & anmelden',
    }
  },
})