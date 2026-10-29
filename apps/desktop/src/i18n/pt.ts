import { defineLocale } from './define-locale'

// Portuguese (pt) — partial locale. Missing desktop-only strings fall back to
// English via defineLocale(); new keys remain type-checked by Translations.
export const pt = defineLocale({
  common: {
    apply: 'Aplicar',
    back: 'Voltar',
    save: 'Guardar',
    saving: 'A guardar…',
    cancel: 'Cancelar',
    change: 'Alterar',
    choose: 'Escolher',
    clear: 'Limpar',
    close: 'Fechar',
    collapse: 'Recolher',
    confirm: 'Confirmar',
    connect: 'Ligar',
    connecting: 'A ligar',
    continue: 'Continuar',
    copied: 'Copiado',
    copy: 'Copiar',
    copyFailed: 'Falha ao copiar',
    delete: 'Eliminar',
    docs: 'Documentação',
    done: 'Concluído',
    error: 'Erro',
    expand: 'Expandir',
    failed: 'Falhou',
    formatJson: 'Formatar JSON',
    free: 'Grátis',
    loading: 'A carregar…',
    notSet: 'Não definido',
    refresh: 'Atualizar',
    remove: 'Remover',
    replace: 'Substituir',
    retry: 'Tentar novamente',
    run: 'Executar',
    send: 'Enviar',
    set: 'Definir',
    skip: 'Ignorar',
    update: 'Atualizar',
    tryHint: term => `Tente “${term}”`,
    on: 'Ativado',
    off: 'Desativado'
  },

  fileMenu: {
    revealFinder: 'Mostrar no Finder',
    revealExplorer: 'Mostrar no Explorador de Ficheiros',
    revealFileManager: 'Abrir Pasta Contentora',
    revealInSidebar: 'Mostrar na árvore de ficheiros',
    copyPath: 'Copiar Caminho',
    copyRelativePath: 'Copiar Caminho Relativo',
    rename: 'Renomear…',
    delete: 'Eliminar',
    renameTitle: 'Renomear',
    renameLabel: 'Novo nome',
    deleteTitle: name => `Eliminar ${name}?`,
    deleteBody: 'Será movido para o Cesto — pode restaurá-lo a partir daí.',
    pathCopied: 'Caminho copiado'
  },

  boot: {
    ready: 'OpenAmer Desktop está pronto',
    desktopBootFailedWithMessage: message => `Falha ao iniciar o ambiente de trabalho: ${message}`,
    steps: {
      connectingGateway: 'A ligar ao gateway do ambiente de trabalho',
      loadingSettings: 'A carregar as configurações do OpenAmer',
      loadingSessions: 'A carregar sessões recentes',
      startingDesktopConnection: 'A iniciar ligação do ambiente de trabalho',
      startingOpenAmerDesktop: 'A iniciar o OpenAmer Desktop…'
    },
    errors: {
      backgroundExited: 'O processo em segundo plano do OpenAmer terminou.',
      backgroundExitedDuringStartup: 'O processo em segundo plano do OpenAmer terminou durante o arranque.',
      backendStopped: 'O backend parou',
      desktopBootFailed: 'Falha ao iniciar o ambiente de trabalho',
      gatewayConnectionLost: 'Ligação ao gateway perdida',
      gatewaySignInRequired: 'Início de sessão no gateway necessário',
      ipcBridgeUnavailable: 'A ponte IPC do ambiente de trabalho não está disponível.'
    },
    failure: {
      title: 'O OpenAmer não conseguiu iniciar',
      description:
        'O gateway em segundo plano não arrancou. Experimente um dos passos de recuperação abaixo. Nada aqui apaga os seus chats ou configurações.',
      remoteTitle: 'Início de sessão no gateway remoto necessário',
      remoteDescription:
        'A sua sessão do gateway remoto expirou. Inicie sessão novamente para voltar a ligar. Nada aqui apaga os seus chats ou configurações.',
      retry: 'Tentar novamente',
      repairInstall: 'Reparar instalação',
      useLocalGateway: 'Usar gateway local',
      gatewaySettings: 'Configurações do gateway',
      back: 'Voltar',
      openLogs: 'Abrir registos',
      repairHint: 'A reparação volta a executar o instalador e pode demorar alguns minutos numa máquina nova.',
      remoteSignInHint: signInLabel =>
        `Termina a sessão guardada do navegador remoto e depois abre ${signInLabel}. Use "Usar gateway local" para mudar para o backend incluído.`,
      signOutAndSignIn: 'Terminar sessão e iniciar sessão',
      remoteFailureHint:
        'Verifique o URL e o início de sessão nas configurações do gateway, ou mude para o gateway local.',
      hideRecentLogs: 'Ocultar registos recentes',
      showRecentLogs: 'Mostrar registos recentes',
      signedInTitle: 'Sessão iniciada',
      signedInMessage: 'A voltar a ligar ao gateway remoto…',
      signInIncompleteTitle: 'Início de sessão incompleto',
      signInIncompleteMessage: 'A janela de início de sessão fechou antes de a autenticação terminar.',
      signInFailed: 'Falha no início de sessão',
      signInToRemoteGateway: 'Iniciar sessão no gateway remoto',
      signInWithProvider: provider => `Iniciar sessão com ${provider}`,
      identityProvider: 'o seu fornecedor de identidade'
    }
  },

  notifications: {
    region: 'Notificações',
    hide: 'Ocultar',
    show: 'Mostrar',
    more: count => `Mais ${count} notificação${count === 1 ? '' : 'ões'}`,
    clearAll: 'Limpar tudo',
    dismiss: 'Dispensar notificação',
    details: 'Detalhes',
    copyDetail: 'Copiar detalhe',
    copyDetailFailed: 'Não foi possível copiar o detalhe da notificação',
    backendOutOfDateTitle: 'Backend desatualizado',
    backendOutOfDateMessage:
      'O seu backend do OpenAmer é mais antigo do que esta versão do ambiente de trabalho e pode não funcionar corretamente. Atualize para alinhá-los.',
    installMethodUnsupportedTitle: 'Método de instalação não suportado',
    updateOpenAmer: 'Atualizar OpenAmer',
    updateReadyTitle: 'Atualização pronta',
    updateReadyMessage: count => `${count} alteração${count === 1 ? '' : 'ões'} disponível${count === 1 ? '' : 'is'}.`,
    seeWhatsNew: 'Ver novidades',
    errors: {
      elevenLabsNeedsKey: 'ElevenLabs STT precisa de ELEVENLABS_API_KEY.',
      elevenLabsRejectedKey: 'ElevenLabs rejeitou a chave de API (401).',
      gatewayAuthFailed: 'Falha de autenticação do gateway — verifique a sua API_SERVER_KEY.',
      methodNotAllowed:
        'O backend do ambiente de trabalho rejeitou esse pedido (405 Method Not Allowed). Tente reiniciar o OpenAmer Desktop.',
      microphonePermission: 'A permissão do microfone foi recusada.',
      openaiRejectedApiKey: 'A OpenAI rejeitou a chave de API.',
      openaiRejectedApiKeyWithStatus: status => `A OpenAI rejeitou a chave de API (${status} invalid_api_key).`,
      openaiTtsNeedsKey: 'OpenAI TTS precisa de VOICE_TOOLS_OPENAI_KEY ou OPENAI_API_KEY.'
    },
    voice: {
      configureSpeechToText: 'Configure a voz para texto para usar o modo de voz.',
      couldNotStartSession: 'Não foi possível iniciar a sessão de voz',
      microphoneAccessDenied: 'Acesso ao microfone recusado.',
      microphoneConstraintsUnsupported: 'As restrições de microfone não são suportadas neste dispositivo.',
      microphoneFailed: 'Falha no microfone',
      microphoneInUse: 'O microfone já está a ser usado por outra aplicação.',
      microphonePermissionDenied: 'A permissão do microfone foi recusada.',
      microphoneStartFailed: 'Não foi possível iniciar a gravação do microfone.',
      microphoneUnsupported: 'Este ambiente não suporta gravação de microfone.',
      noMicrophone: 'Nenhum microfone encontrado.',
      noSpeechDetected: 'Nenhuma voz detetada',
      playbackFailed: 'Falha na reprodução de voz',
      recordingFailed: 'Falha na gravação de voz',
      transcriptionFailed: 'Falha na transcrição de voz',
      transcriptionUnavailable: 'A transcrição de voz ainda não está disponível.',
      tryRecordingAgain: 'Tente gravar novamente.',
      unavailable: 'Voz indisponível'
    },
    native: {
      approvalTitle: 'Aprovação necessária',
      approveAction: 'Aprovar',
      rejectAction: 'Rejeitar',
      inputTitle: 'Entrada necessária',
      inputBody: 'O OpenAmer está à espera da sua resposta.',
      turnDoneTitle: 'OpenAmer terminou',
      turnDoneBody: 'A resposta está pronta.',
      turnErrorTitle: 'O turno falhou',
      backgroundDoneTitle: 'Tarefa em segundo plano concluída',
      backgroundFailedTitle: 'A tarefa em segundo plano falhou',
      creditsTitle: 'Créditos'
    }
  },

  billingBlock: {
    titleOpenamer: 'Sem créditos do OpenAmer',
    titleProvider: provider => `Sem créditos — ${provider}`,
    fallbackMessage: 'A sua conta está sem créditos. Adicione créditos para continuar.',
    openBilling: 'Abrir faturação',
    addCredits: 'Adicionar créditos',
    dismiss: 'Dispensar'
  },

  titlebar: {
    hideSidebar: 'Ocultar barra lateral',
    showSidebar: 'Mostrar barra lateral',
    search: 'Pesquisar',
    searchTitle: 'Pesquisar sessões, vistas e ações',
    swapSidebarSides: 'Trocar o lado da barra lateral',
    swapSidebarSidesTitle: 'Trocar os lados das sessões e do navegador de ficheiros',
    hideRightSidebar: 'Ocultar barra lateral direita',
    showRightSidebar: 'Mostrar barra lateral direita',
    muteHaptics: 'Silenciar háptica',
    unmuteHaptics: 'Ativar háptica',
    openSettings: 'Abrir configurações',
    openStarmap: 'Abrir grafo de memória',
    openKeybinds: 'Atalhos de teclado',
    layoutEditor: 'Editor de disposição',
    layoutEditorTitle: 'Editor de disposição — Cmd/Ctrl+clique repõe a disposição'
  },

  language: {
    label: 'Idioma',
    description: 'Escolha o idioma da interface do ambiente de trabalho.',
    saving: 'A guardar o idioma…',
    saveError: 'Falha ao atualizar o idioma',
    switchTo: 'Mudar de idioma',
    searchPlaceholder: 'Pesquisar idiomas…',
    noResults: 'Nenhum idioma encontrado'
  },

  settings: {
    closeSettings: 'Fechar configurações',
    exportConfig: 'Exportar configuração',
    importConfig: 'Importar configuração',
    resetToDefaults: 'Restaurar predefinições',
    resetConfirm: 'Restaurar todas as configurações para as predefinições do OpenAmer?',
    exportFailed: 'Falha na exportação',
    resetFailed: 'Falha na reposição',
    nav: {
      providers: 'Fornecedores',
      providerAccounts: 'Contas',
      providerApiKeys: 'Chaves de API',
      providerCustomEndpoints: 'Endpoints Personalizados',
      gateway: 'Gateway',
      apiKeys: 'Ferramentas e Chaves',
      keybinds: 'Atalhos de Teclado',
      keysTools: 'Ferramentas',
      keysSettings: 'Configurações',
      mcp: 'MCP',
      archivedChats: 'Chats Arquivados',
      about: 'Sobre',
      billing: 'Faturação',
      notifications: 'Notificações',
      plugins: 'Plugins'
    },
    sections: {
      model: 'Modelo',
      chat: 'Conversa',
      appearance: 'Aparência',
      workspace: 'Espaço de trabalho',
      safety: 'Segurança',
      memory: 'Memória e Contexto',
      voice: 'Voz',
      advanced: 'Avançado'
    },
    modeOptions: {
      light: { label: 'Claro', description: 'Superfícies luminosas' },
      dark: { label: 'Escuro', description: 'Espaço com pouco brilho' },
      system: { label: 'Sistema', description: 'Seguir a aparência do sistema' }
    },
    appearance: {
      title: 'Aparência',
      intro:
        'Estas são preferências de visualização apenas do ambiente de trabalho. O modo controla o brilho; o tema controla a paleta de acentos e o estilo da conversa.',
      colorMode: 'Modo de Cor',
      colorModeDesc: 'Escolha um modo fixo ou deixe o OpenAmer seguir a configuração do seu sistema.',
      toolViewTitle: 'Apresentação de Chamadas de Ferramentas',
      toolViewDesc: 'Produto oculta os dados brutos das ferramentas; Técnico mostra entrada/saída completas.',
      uiScaleTitle: 'Escala da Interface',
      uiScaleDesc: (percent: number) =>
        `Escala o texto e os controlos em toda a aplicação. Cmd/Ctrl com +, - e 0 também funciona. Atual: ${percent}%.`,
      translucencyTitle: 'Transparência da Janela',
      translucencyDesc: 'Veja o seu ambiente de trabalho através da janela. Apenas em macOS e Windows.',
      backdropTitle: 'Fundo da Conversa',
      backdropDesc: 'A ténue imagem de estátua atrás da conversação.',
      embedsTitle: 'Conteúdos Incorporados',
      embedsDesc:
        'As pré-visualizações carregam de sites de terceiros (YouTube, X, …). Perguntar mostra um marcador até permitir cada um; Sempre carrega-os automaticamente; Desligado mantém apenas links.',
      embedsAsk: 'Perguntar',
      embedsAlways: 'Sempre',
      embedsOff: 'Desligado',
      embedsReset: (count: number) =>
        `Restaurar ${count} serviço${count === 1 ? '' : 's'} permitido${count === 1 ? '' : 's'}`,
      product: 'Produto',
      productDesc: 'Atividade de ferramentas amigável com resumos concisos.',
      technical: 'Técnico',
      technicalDesc: 'Inclui argumentos/resultados brutos e detalhes de baixo nível.',
      themeTitle: 'Tema',
      themeDesc: 'Apenas paletas do ambiente de trabalho. O modo selecionado é aplicado por cima.',
      themeProfileNote: profile => `Guardado para o perfil ${profile} — cada perfil mantém o seu próprio tema.`,
      installTitle: 'Instalar do VS Code',
      installDesc:
        'Cole um id de extensão do Marketplace (p. ex. dracula-theme.theme-dracula) para converter o seu tema de cores numa paleta do ambiente de trabalho.',
      installPlaceholder: 'publisher.extension',
      installButton: 'Instalar',
      installing: 'A instalar…',
      installError: 'Não foi possível instalar esse tema.',
      installed: name => `“${name}” instalado.`,
      removeTheme: 'Remover tema',
      importedBadge: 'Importado'
    },
    about: {
      heading: 'OpenAmer Desktop',
      version: value => `Versão ${value}`,
      versionUnavailable: 'Versão indisponível',
      updates: 'Atualizações',
      checkNow: 'Verificar agora',
      checking: 'A verificar…',
      seeWhatsNew: 'Ver novidades',
      updateNow: 'Atualizar agora',
      releaseNotes: 'Notas de versão',
      onLatest: 'Está na versão mais recente.',
      installing: 'Uma atualização está a ser instalada.',
      cantUpdate: 'Esta compilação não se consegue atualizar de dentro da aplicação.',
      cantReach: 'Não conseguimos contactar o servidor de atualizações.',
      tapCheck: 'Toque em "Verificar agora" para procurar atualizações.',
      updateReady: count =>
        `Uma nova atualização está pronta (${count} alteração${count === 1 ? '' : 'ões'} incluída${count === 1 ? '' : 's'}).`,
      lastChecked: age => `Verificado pela última vez ${age}`,
      justNowSuffix: ' · neste momento',
      automaticUpdates: 'Atualizações automáticas',
      automaticUpdatesDesc:
        'O OpenAmer procura atualizações automaticamente em segundo plano e avisa quando uma está pronta.',
      branchCommit: (branch, commit) => `Ramo ${branch} · Commit ${commit}`,
      never: 'nunca',
      justNow: 'neste momento',
      minAgo: count => `há ${count} min`,
      hoursAgo: count => `há ${count} horas`,
      daysAgo: count => `há ${count} dias`
    }
  }
})
