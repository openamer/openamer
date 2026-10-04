import { defineLocale } from './define-locale'

// Lithuanian (lt) — partial locale. Missing desktop-only strings fall back to
// English via defineLocale(); new keys remain type-checked by Translations.
export const lt = defineLocale({
  common: {
    apply: 'Taikyti',
    back: 'Atgal',
    save: 'Įrašyti',
    saving: 'Įrašoma…',
    cancel: 'Atšaukti',
    change: 'Keisti',
    choose: 'Pasirinkti',
    clear: 'Išvalyti',
    close: 'Užverti',
    collapse: 'Suskleisti',
    confirm: 'Patvirtinti',
    connect: 'Prisijungti',
    connecting: 'Jungiamasi',
    continue: 'Tęsti',
    copied: 'Nukopijuota',
    copy: 'Kopijuoti',
    copyFailed: 'Nepavyko nukopijuoti',
    delete: 'Ištrinti',
    docs: 'Dokumentacija',
    done: 'Atlikta',
    error: 'Klaida',
    expand: 'Išskleisti',
    failed: 'Nepavyko',
    formatJson: 'Formatuoti JSON',
    free: 'Nemokama',
    loading: 'Įkeliama…',
    notSet: 'Nenustatyta',
    refresh: 'Atnaujinti',
    remove: 'Šalinti',
    replace: 'Pakeisti',
    retry: 'Bandyti dar kartą',
    run: 'Vykdyti',
    send: 'Siųsti',
    set: 'Nustatyti',
    skip: 'Praleisti',
    update: 'Atnaujinti',
    tryHint: term => `Išbandykite „${term}“`,
    on: 'Įjungta',
    off: 'Išjungta'
  },

  fileMenu: {
    revealFinder: 'Rodyti „Finder“',
    revealExplorer: 'Rodyti „File Explorer“',
    revealFileManager: 'Atverti aplanką su failu',
    revealInSidebar: 'Rodyti failų medyje',
    copyPath: 'Kopijuoti kelią',
    copyRelativePath: 'Kopijuoti santykinį kelią',
    rename: 'Pervadinti…',
    delete: 'Ištrinti',
    renameTitle: 'Pervadinti',
    renameLabel: 'Naujas pavadinimas',
    deleteTitle: name => `Ištrinti ${name}?`,
    deleteBody: 'Jis bus perkeltas į šiukšlinę — iš ten galėsite atkurti.',
    pathCopied: 'Kelias nukopijuotas'
  },

  boot: {
    ready: 'OpenAmer Desktop paruoštas',
    desktopBootFailedWithMessage: message => `Nepavyko paleisti darbalaukio: ${message}`,
    steps: {
      connectingGateway: 'Jungiamasi prie darbalaukio šliuzo',
      loadingSettings: 'Įkeliami OpenAmer nustatymai',
      loadingSessions: 'Įkeliami neseniai naudoti seansai',
      startingDesktopConnection: 'Paleidžiamas darbalaukio ryšys',
      startingOpenAmerDesktop: 'Paleidžiamas OpenAmer Desktop…'
    },
    errors: {
      backgroundExited: 'OpenAmer foninis procesas baigė darbą.',
      backgroundExitedDuringStartup: 'OpenAmer foninis procesas baigė darbą paleisties metu.',
      backendStopped: 'Vidinė dalis sustojo',
      desktopBootFailed: 'Nepavyko paleisti darbalaukio',
      gatewayConnectionLost: 'Ryšys su šliuzu prarastas',
      gatewaySignInRequired: 'Reikia prisijungti prie šliuzo',
      ipcBridgeUnavailable: 'Darbalaukio IPC tiltas neprieinamas.'
    },
    failure: {
      title: 'OpenAmer nepavyko paleisti',
      description:
        'Foninis šliuzas nepaleido. Pabandykite vieną iš žemiau esančių atkūrimo veiksmų. Joks veiksmas čia neištrina jūsų pokalbių ar nustatymų.',
      remoteTitle: 'Reikia prisijungti prie nuotolinio šliuzo',
      remoteDescription:
        'Jūsų nuotolinio šliuzo seansas pasibaigė. Prisijunkite iš naujo, kad vėl prisijungtumėte. Joks veiksmas čia neištrina jūsų pokalbių ar nustatymų.',
      retry: 'Bandyti dar kartą',
      repairInstall: 'Sutaisyti įdiegtį',
      useLocalGateway: 'Naudoti vietinį šliuzą',
      gatewaySettings: 'Šliuzo nustatymai',
      back: 'Atgal',
      openLogs: 'Atverti žurnalus',
      repairHint: 'Taisymas iš naujo paleidžia diegimo programą ir naujoje mašinoje gali užimti kelias minutes.',
      remoteSignInHint: signInLabel =>
        `Užbaigia išsaugotą nuotolinio naršyklės seansą ir tada atveria ${signInLabel}. Naudokite „Naudoti vietinį šliuzą“, kad pereitumėte prie integruotos vidinės dalies.`,
      signOutAndSignIn: 'Atsijungti ir prisijungti',
      remoteFailureHint: 'Patikrinkite URL ir prisijungimą šliuzo nustatymuose, arba pereikite prie vietinio šliuzo.',
      hideRecentLogs: 'Slėpti naujausius žurnalus',
      showRecentLogs: 'Rodyti naujausius žurnalus',
      signedInTitle: 'Prisijungta',
      signedInMessage: 'Iš naujo jungiamasi prie nuotolinio šliuzo…',
      signInIncompleteTitle: 'Prisijungimas nebaigtas',
      signInIncompleteMessage: 'Prisijungimo langas užsidarė iki autentifikacijos pabaigos.',
      signInFailed: 'Prisijungimas nepavyko',
      signInToRemoteGateway: 'Prisijungti prie nuotolinio šliuzo',
      signInWithProvider: provider => `Prisijungti per ${provider}`,
      identityProvider: 'savą tapatybės teikėją'
    }
  },

  notifications: {
    region: 'Pranešimai',
    hide: 'Slėpti',
    show: 'Rodyti',
    more: count => (count === 1 ? 'Dar 1 pranešimas' : `Dar ${count} pranešimų`),
    clearAll: 'Išvalyti viską',
    dismiss: 'Uždaryti pranešimą',
    details: 'Išsami informacija',
    copyDetail: 'Kopijuoti išsamią informaciją',
    copyDetailFailed: 'Nepavyko nukopijuoti pranešimo informacijos',
    backendOutOfDateTitle: 'Vidinė dalis pasenusi',
    backendOutOfDateMessage:
      'Jūsų OpenAmer vidinė dalis senesnė už šią darbalaukio versiją ir gali veikti netinkamai. Atnaujinkite, kad jos sutaptų.',
    installMethodUnsupportedTitle: 'Įdiegimo būdas nepalaikomas',
    updateOpenAmer: 'Atnaujinti OpenAmer',
    updateReadyTitle: 'Atnaujinimas paruoštas',
    updateReadyMessage: count => (count === 1 ? 'Pasiekiama 1 pakeitimas.' : `Pasiekiami ${count} pakeitimai.`),
    seeWhatsNew: 'Peržiūrėti naujienas',
    errors: {
      elevenLabsNeedsKey: 'ElevenLabs STT reikia ELEVENLABS_API_KEY.',
      elevenLabsRejectedKey: 'ElevenLabs atmetė API raktą (401).',
      gatewayAuthFailed: 'Šliuzo autentifikacija nepavyko — patikrinkite savo API_SERVER_KEY.',
      methodNotAllowed:
        'Darbalaukio vidinė dalis atmetė šią užklausą (405 Method Not Allowed). Pabandykite paleisti OpenAmer Desktop iš naujo.',
      microphonePermission: 'Mikrofono leidimas atmestas.',
      openaiRejectedApiKey: 'OpenAI atmetė API raktą.',
      openaiRejectedApiKeyWithStatus: status => `OpenAI atmetė API raktą (${status} invalid_api_key).`,
      openaiTtsNeedsKey: 'OpenAI TTS reikia VOICE_TOOLS_OPENAI_KEY arba OPENAI_API_KEY.'
    },
    voice: {
      configureSpeechToText: 'Sukonfigūruokite kalbą į tekstą, kad naudotumėte balso režimą.',
      couldNotStartSession: 'Nepavyko pradėti balso seanso',
      microphoneAccessDenied: 'Prieiga prie mikrofono atmesta.',
      microphoneConstraintsUnsupported: 'Mikrofono apribojimai šiame įrenginyje nepalaikomi.',
      microphoneFailed: 'Mikrofono klaida',
      microphoneInUse: 'Mikrofoną jau naudoja kita programa.',
      microphonePermissionDenied: 'Mikrofono leidimas atmestas.',
      microphoneStartFailed: 'Nepavyko pradėti mikrofono įrašymo.',
      microphoneUnsupported: 'Ši aplinka nepalaiko mikrofono įrašymo.',
      noMicrophone: 'Mikrofonas nerastas.',
      noSpeechDetected: 'Kalbos neaptikta',
      playbackFailed: 'Balso atkūrimas nepavyko',
      recordingFailed: 'Balso įrašymas nepavyko',
      transcriptionFailed: 'Balso transkribavimas nepavyko',
      transcriptionUnavailable: 'Balso transkribavimas dar neprieinamas.',
      tryRecordingAgain: 'Pabandykite įrašyti dar kartą.',
      unavailable: 'Balsas neprieinamas'
    },
    native: {
      approvalTitle: 'Reikia patvirtinimo',
      approveAction: 'Patvirtinti',
      rejectAction: 'Atmesti',
      inputTitle: 'Reikia įvesties',
      inputBody: 'OpenAmer laukia jūsų atsakymo.',
      turnDoneTitle: 'OpenAmer baigė',
      turnDoneBody: 'Atsakymas paruoštas.',
      turnErrorTitle: 'Ciklas nepavyko',
      backgroundDoneTitle: 'Foninė užduotis atlikta',
      backgroundFailedTitle: 'Foninė užduotis nepavyko',
      creditsTitle: 'Kreditai'
    }
  },

  billingBlock: {
    titleOpenamer: 'Nėra OpenAmer kreditų',
    titleProvider: provider => `Nėra kreditų — ${provider}`,
    fallbackMessage: 'Jūsų paskyroje nėra kreditų. Įkelkite kreditų, kad galėtumėte tęsti.',
    openBilling: 'Atverti sąskaitas',
    addCredits: 'Įkelti kreditų',
    dismiss: 'Uždaryti'
  },

  titlebar: {
    hideSidebar: 'Slėpti šoninę juostą',
    showSidebar: 'Rodyti šoninę juostą',
    search: 'Ieškoti',
    searchTitle: 'Ieškoti seansų, rodinių ir veiksmų',
    swapSidebarSides: 'Sukeisti šoninės juostos pusę',
    swapSidebarSidesTitle: 'Sukeisti seansų ir failų naršyklės puses',
    hideRightSidebar: 'Slėpti dešinę šoninę juostą',
    showRightSidebar: 'Rodyti dešinę šoninę juostą',
    muteHaptics: 'Išjungti haptiką',
    unmuteHaptics: 'Įjungti haptiką',
    openSettings: 'Atverti nustatymus',
    openStarmap: 'Atverti atminties grafą',
    openKeybinds: 'Spartieji klavišai',
    layoutEditor: 'Išdėstymo rengyklė',
    layoutEditorTitle: 'Išdėstymo rengyklė — Cmd/Ctrl+spustelėjimas atkuria išdėstymą'
  },

  language: {
    label: 'Kalba',
    description: 'Pasirinkite darbalaukio sąsajos kalbą.',
    saving: 'Įrašoma kalba…',
    saveError: 'Nepavyko atnaujinti kalbos',
    switchTo: 'Pakeisti kalbą',
    searchPlaceholder: 'Ieškoti kalbų…',
    noResults: 'Kalbų nerasta'
  },

  settings: {
    closeSettings: 'Užverti nustatymus',
    exportConfig: 'Eksportuoti konfigūraciją',
    importConfig: 'Importuoti konfigūraciją',
    resetToDefaults: 'Atkurti numatytuosius nustatymus',
    resetConfirm: 'Atkurti visus nustatymus į OpenAmer numatytuosius?',
    exportFailed: 'Eksportas nepavyko',
    resetFailed: 'Atkūrimas nepavyko',
    nav: {
      providers: 'Teikėjai',
      providerAccounts: 'Paskyros',
      providerApiKeys: 'API raktai',
      providerCustomEndpoints: 'Pasirinktiniai galiniai taškai',
      gateway: 'Šliuzas',
      apiKeys: 'Įrankiai ir raktai',
      keybinds: 'Spartieji klavišai',
      keysTools: 'Įrankiai',
      keysSettings: 'Nustatymai',
      mcp: 'MCP',
      archivedChats: 'Archyvuoti pokalbiai',
      about: 'Apie',
      billing: 'Sąskaitos',
      notifications: 'Pranešimai',
      plugins: 'Įskiepiai'
    },
    sections: {
      model: 'Modelis',
      chat: 'Pokalbis',
      appearance: 'Išvaizda',
      workspace: 'Darbo erdvė',
      safety: 'Sauga',
      memory: 'Atmintis ir kontekstas',
      voice: 'Balsas',
      advanced: 'Išplėstiniai'
    },
    modeOptions: {
      light: { label: 'Šviesus', description: 'Šviesios paviršiai' },
      dark: { label: 'Tamsus', description: 'Erdvė su mažu švytėjimu' },
      system: { label: 'Sistema', description: 'Laikytis sistemos išvaizdos' }
    },
    appearance: {
      title: 'Išvaizda',
      intro:
        'Tai tik darbalaukio rodymo nuostatos. Režimas valdo šviesumą; tema valdo akcentų paletę ir pokalbio stilių.',
      colorMode: 'Spalvų režimas',
      colorModeDesc: 'Pasirinkite fiksuotą režimą arba leiskite OpenAmer laikytis jūsų sistemos nustatymo.',
      toolViewTitle: 'Įrankių iškvietimų pateikimas',
      toolViewDesc: 'Produktas slepia žalius įrankių duomenis; Techninis rodo pilnus įėjimus/išėjimus.',
      uiScaleTitle: 'Sąsajos mastelis',
      uiScaleDesc: (percent: number) =>
        `Keičia teksto ir valdiklių mastelį visoje programoje. Taip pat veikia Cmd/Ctrl su +, - ir 0. Dabartinis: ${percent}%.`,
      translucencyTitle: 'Lango permatomumas',
      translucencyDesc: 'Matykite savo darbalaukį pro langą. Tik macOS ir Windows.',
      backdropTitle: 'Pokalbio fonas',
      backdropDesc: 'Pokalbio fone esantis didelis statulos vaizdas.',
      embedsTitle: 'Įterptas turinys',
      embedsDesc:
        'Peržiūros įkeliamos iš trečiųjų šalių svetainių (YouTube, X, …). Klausiant rodo žymeklį, kol leisite kiekvieną; Visada įkelia automatiškai; Išjungta palieka tik nuorodas.',
      embedsAsk: 'Klausti',
      embedsAlways: 'Visada',
      embedsOff: 'Išjungta',
      embedsReset: (count: number) =>
        count === 1 ? 'Atkurti 1 leistą paslaugą' : `Atkurti ${count} leistus paslaugas`,
      product: 'Produktas',
      productDesc: 'Draugiška įrankių veikla su glaustomis ištraukomis.',
      technical: 'Techninis',
      technicalDesc: 'Įtraukia žalius argumentus/rezultatus ir žemo lygio detales.',
      themeTitle: 'Tema',
      themeDesc: 'Tik darbalaukio paletės. Pasirinktas režimas taikomas ant viršaus.',
      themeProfileNote: profile => `Įrašyta profiliui ${profile} — kiekvienas profilis turi savo temą.`,
      installTitle: 'Įdiegti iš VS Code',
      installDesc:
        'Įklijuokite Marketplace plėtinio ID (pvz. dracula-theme.theme-dracula), kad savo spalvų temą paverstumėte darbalaukio palete.',
      installPlaceholder: 'publisher.extension',
      installButton: 'Įdiegti',
      installing: 'Diegiama…',
      installError: 'Nepavyko įdiegti tos temos.',
      installed: name => `„${name}“ įdiegta.`,
      removeTheme: 'Pašalinti temą',
      importedBadge: 'Importuota'
    },
    about: {
      heading: 'OpenAmer Desktop',
      version: value => `Versija ${value}`,
      versionUnavailable: 'Versija neprieinama',
      updates: 'Atnaujinimai',
      checkNow: 'Tikrinti dabar',
      checking: 'Tikrinama…',
      seeWhatsNew: 'Peržiūrėti naujienas',
      updateNow: 'Atnaujinti dabar',
      releaseNotes: 'Laidos pastabos',
      onLatest: 'Naudojate naujausią versiją.',
      installing: 'Diegiamas atnaujinimas.',
      cantUpdate: 'Šios programos negalima atnaujinti iš viduje.',
      cantReach: 'Nepavyko pasiekti atnaujinimų serverio.',
      tapCheck: 'Bakstelėkite „Tikrinti dabar“, kad ieškotumėte atnaujinimų.',
      updateReady: count =>
        count === 1
          ? 'Naujas atnaujinimas paruoštas (įtrauktas 1 pakeitimas).'
          : `Naujas atnaujinimas paruoštas (įtraukti ${count} pakeitimai).`,
      lastChecked: age => `Paskutinį kartą tikrinta ${age}`,
      justNowSuffix: ' · dabar',
      automaticUpdates: 'Automatiniai atnaujinimai',
      automaticUpdatesDesc:
        'OpenAmer foniniu režimu automatiškai tikrina atnaujinimus ir įspėja, kai vienas paruoštas.',
      branchCommit: (branch, commit) => `Šaka ${branch} · Commit ${commit}`,
      never: 'niekada',
      justNow: 'dabar',
      minAgo: count => `prieš ${count} min`,
      hoursAgo: count => `prieš ${count} valandas`,
      daysAgo: count => `prieš ${count} dienų`
    }
  }
})
