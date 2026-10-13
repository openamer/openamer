import { defineLocale } from './define-locale'

export const es = defineLocale({
  common: {
    apply: 'Aplicar',
    back: 'Atrás',
    save: 'Guardar',
    saving: 'Guardando…',
    cancel: 'Cancelar',
    change: 'Cambiar',
    choose: 'Elegir',
    clear: 'Limpiar',
    close: 'Cerrar',
    collapse: 'Contraer',
    confirm: 'Confirmar',
    connect: 'Conectar',
    connecting: 'Conectando',
    continue: 'Continuar',
    copied: 'Copiado',
    copy: 'Copiar',
    copyFailed: 'No se pudo copiar',
    delete: 'Eliminar',
    docs: 'Documentación',
    done: 'Hecho',
    error: 'Error',
    expand: 'Expandir',
    failed: 'Error',
    formatJson: 'Formatear JSON',
    free: 'Gratis',
    loading: 'Cargando…',
    notSet: 'Sin configurar',
    refresh: 'Actualizar',
    remove: 'Quitar',
    replace: 'Reemplazar',
    retry: 'Reintentar',
    run: 'Ejecutar',
    send: 'Enviar',
    set: 'Establecer',
    skip: 'Omitir',
    update: 'Actualizar',
    tryHint: term => `Prueba con “${term}”`,
    on: 'Activado',
    off: 'Desactivado'
  },

  fileMenu: {
    revealFinder: 'Mostrar en Finder',
    revealExplorer: 'Mostrar en el Explorador de archivos',
    revealFileManager: 'Abrir carpeta contenedora',
    revealInSidebar: 'Mostrar en el árbol de archivos',
    copyPath: 'Copiar ruta',
    copyRelativePath: 'Copiar ruta relativa',
    rename: 'Renombrar…',
    delete: 'Eliminar',
    renameTitle: 'Renombrar',
    renameLabel: 'Nuevo nombre',
    deleteTitle: name => `¿Eliminar ${name}?`,
    deleteBody: 'Se moverá a la Papelera — puedes restaurarlo desde allí.',
    pathCopied: 'Ruta copiada'
  },

  boot: {
    ready: 'OpenAmer Desktop está listo',
    desktopBootFailedWithMessage: message => `Error al iniciar el escritorio: ${message}`,
    steps: {
      connectingGateway: 'Conectando con la pasarela del escritorio',
      loadingSettings: 'Cargando la configuración de OpenAmer',
      loadingSessions: 'Cargando sesiones recientes',
      startingDesktopConnection: 'Iniciando conexión de escritorio',
      startingOpenAmerDesktop: 'Iniciando OpenAmer Desktop…'
    },
    errors: {
      backgroundExited: 'El proceso en segundo plano de OpenAmer finalizó.',
      backgroundExitedDuringStartup: 'El proceso en segundo plano de OpenAmer finalizó durante el arranque.',
      backendStopped: 'El backend se detuvo',
      desktopBootFailed: 'Error al iniciar el escritorio',
      gatewayConnectionLost: 'Se perdió la conexión con la pasarela',
      gatewaySignInRequired: 'Se requiere iniciar sesión en la pasarela',
      ipcBridgeUnavailable: 'El puente IPC del escritorio no está disponible.'
    },
    failure: {
      title: 'OpenAmer no pudo iniciarse',
      description:
        'La pasarela en segundo plano no arrancó. Prueba uno de los pasos de recuperación indicados abajo. Aquí no se eliminan tus chats ni tu configuración.',
      remoteTitle: 'Se requiere iniciar sesión en la pasarela remota',
      remoteDescription:
        'Tu sesión de la pasarela remota ha expirado. Vuelve a iniciar sesión para reconectar. Aquí no se eliminan tus chats ni tu configuración.',
      retry: 'Reintentar',
      repairInstall: 'Reparar instalación',
      useLocalGateway: 'Usar pasarela local',
      gatewaySettings: 'Ajustes de la pasarela',
      back: 'Atrás',
      openLogs: 'Abrir registros',
      repairHint: 'La reparación vuelve a ejecutar el instalador y puede tardar unos minutos en una máquina nueva.',
      remoteSignInHint: signInLabel =>
        `Cierra la sesión guardada del navegador remoto y abre ${signInLabel}. Usa "Usar pasarela local" para cambiar al backend incluido.`,
      signOutAndSignIn: 'Cerrar sesión e iniciar sesión',
      remoteFailureHint: 'Comprueba la URL y el inicio de sesión en los ajustes de la pasarela, o cambia a la pasarela local.',
      hideRecentLogs: 'Ocultar registros recientes',
      showRecentLogs: 'Mostrar registros recientes',
      signedInTitle: 'Sesión iniciada',
      signedInMessage: 'Reconectando con la pasarela remota…',
      signInIncompleteTitle: 'Inicio de sesión incompleto',
      signInIncompleteMessage: 'La ventana de inicio de sesión se cerró antes de terminar la autenticación.',
      signInFailed: 'Error al iniciar sesión',
      signInToRemoteGateway: 'Iniciar sesión en la pasarela remota',
      signInWithProvider: provider => `Iniciar sesión con ${provider}`,
      identityProvider: 'tu proveedor de identidad'
    }
  },

  notifications: {
    region: 'Notificaciones',
    hide: 'Ocultar',
    show: 'Mostrar',
    more: count => `${count} notificación${count === 1 ? '' : 'es'} más`,
    clearAll: 'Borrar todo',
    dismiss: 'Descartar notificación',
    details: 'Detalles',
    copyDetail: 'Copiar detalle',
    copyDetailFailed: 'No se pudo copiar el detalle de la notificación',
    backendOutOfDateTitle: 'Backend desactualizado',
    backendOutOfDateMessage:
      'Tu backend de OpenAmer es más antiguo que esta versión de escritorio y puede no funcionar correctamente. Actualízalo para alinearlos.',
    installMethodUnsupportedTitle: 'Método de instalación no compatible',
    updateOpenAmer: 'Actualizar OpenAmer',
    updateReadyTitle: 'Actualización lista',
    updateReadyMessage: count => `${count} cambio${count === 1 ? '' : 's'} disponible${count === 1 ? '' : 's'}.`,
    seeWhatsNew: 'Ver novedades',
    errors: {
      elevenLabsNeedsKey: 'ElevenLabs STT necesita ELEVENLABS_API_KEY.',
      elevenLabsRejectedKey: 'ElevenLabs rechazó la clave de API (401).',
      gatewayAuthFailed: 'Error de autenticación de la pasarela — revisa tu API_SERVER_KEY.',
      methodNotAllowed:
        'El backend del escritorio rechazó esa solicitud (405 Method Not Allowed). Prueba a reiniciar OpenAmer Desktop.',
      microphonePermission: 'Se denegó el permiso del micrófono.',
      openaiRejectedApiKey: 'OpenAI rechazó la clave de API.',
      openaiRejectedApiKeyWithStatus: status => `OpenAI rechazó la clave de API (${status} invalid_api_key).`,
      openaiTtsNeedsKey: 'OpenAI TTS necesita VOICE_TOOLS_OPENAI_KEY o OPENAI_API_KEY.'
    },
    voice: {
      configureSpeechToText: 'Configura la voz a texto para usar el modo de voz.',
      couldNotStartSession: 'No se pudo iniciar la sesión de voz',
      microphoneAccessDenied: 'Acceso al micrófono denegado.',
      microphoneConstraintsUnsupported: 'Las restricciones de micrófono no son compatibles con este dispositivo.',
      microphoneFailed: 'Error en el micrófono',
      microphoneInUse: 'El micrófono ya está en uso por otra aplicación.',
      microphonePermissionDenied: 'Se denegó el permiso del micrófono.',
      microphoneStartFailed: 'No se pudo iniciar la grabación del micrófono.',
      microphoneUnsupported: 'Este entorno no admite la grabación de micrófono.',
      noMicrophone: 'No se encontró ningún micrófono.',
      noSpeechDetected: 'No se detectó voz',
      playbackFailed: 'Error en la reproducción de voz',
      recordingFailed: 'Error en la grabación de voz',
      transcriptionFailed: 'Error en la transcripción de voz',
      transcriptionUnavailable: 'La transcripción de voz aún no está disponible.',
      tryRecordingAgain: 'Prueba a grabar de nuevo.',
      unavailable: 'Voz no disponible'
    },
    native: {
      approvalTitle: 'Aprobación necesaria',
      approveAction: 'Aprobar',
      rejectAction: 'Rechazar',
      inputTitle: 'Entrada necesaria',
      inputBody: 'OpenAmer espera tu respuesta.',
      turnDoneTitle: 'OpenAmer terminó',
      turnDoneBody: 'La respuesta está lista.',
      turnErrorTitle: 'El turno falló',
      backgroundDoneTitle: 'Tarea en segundo plano finalizada',
      backgroundFailedTitle: 'La tarea en segundo plano falló',
      creditsTitle: 'Créditos'
    }
  },

  billingBlock: {
    titleOpenamer: 'Sin créditos de OpenAmer',
    titleProvider: provider => `Sin créditos — ${provider}`,
    fallbackMessage: 'Tu cuenta no tiene créditos. Añade créditos para continuar.',
    openBilling: 'Abrir facturación',
    addCredits: 'Añadir créditos',
    dismiss: 'Descartar'
  },

  titlebar: {
    hideSidebar: 'Ocultar barra lateral',
    showSidebar: 'Mostrar barra lateral',
    search: 'Buscar',
    searchTitle: 'Buscar sesiones, vistas y acciones',
    swapSidebarSides: 'Cambiar el lado de la barra lateral',
    swapSidebarSidesTitle: 'Intercambiar los lados de sesiones y navegador de archivos',
    hideRightSidebar: 'Ocultar barra lateral derecha',
    showRightSidebar: 'Mostrar barra lateral derecha',
    muteHaptics: 'Silenciar háptica',
    unmuteHaptics: 'Activar háptica',
    openSettings: 'Abrir ajustes',
    openStarmap: 'Abrir grafo de memoria',
    openKeybinds: 'Atajos de teclado',
    layoutEditor: 'Editor de diseño',
    layoutEditorTitle: 'Editor de diseño — Cmd+clic restablece el diseño'
  },

  keybinds: {
    title: 'Atajos de teclado',
    subtitle: open => `Haz clic en un atajo para reasignarlo · ${open} vuelve a abrir este panel.`,
    search: 'Buscar atajos…',
    rebind: 'Reasignar',
    reset: 'Restablecer al valor predeterminado',
    resetAll: 'Restablecer todo',
    pressKey: 'Pulsa una tecla…',
    set: 'asignado',
    conflictWith: label => `También asignado a “${label}”`,
    categories: {
      composer: 'Compositor',
      profiles: 'Perfiles',
      session: 'Sesión',
      navigation: 'Navegación',
      view: 'Vista'
    },
    actions: {
      'keybinds.openPanel': 'Abrir atajos de teclado',
      'nav.commandPalette': 'Abrir paleta de comandos',
      'nav.commandCenter': 'Abrir centro de comandos',
      'nav.settings': 'Abrir ajustes',
      'nav.profiles': 'Abrir perfiles',
      'nav.skills': 'Abrir capacidades',
      'nav.messaging': 'Abrir mensajería',
      'nav.artifacts': 'Abrir artefactos',
      'nav.cron': 'Abrir trabajos programados',
      'nav.agents': 'Abrir agentes',
      'session.new': 'Nueva sesión',
      'session.newTab': 'Nueva pestaña de sesión',
      'session.newWindow': 'Nueva ventana',
      'session.next': 'Siguiente sesión',
      'session.prev': 'Sesión anterior',
      'session.focusSearch': 'Buscar sesiones',
      'session.togglePin': 'Fijar / desfijar la sesión actual',
      'workspace.newWorktree': 'Nuevo worktree',
      'composer.focus': 'Enfocar el compositor',
      'composer.modelPicker': 'Abrir selector de modelo',
      'composer.voice': 'Iniciar / detener conversación de voz',
      'view.toggleSidebar': 'Alternar barra lateral de sesiones',
      'view.toggleRightSidebar': 'Alternar navegador de archivos',
      'view.toggleReview': 'Alternar panel de revisión',
      'view.showFiles': 'Mostrar navegador de archivos',
      'view.showTerminal': 'Alternar terminal',
      'view.newTerminal': 'Nueva terminal',
      'view.nextTerminal': 'Siguiente terminal',
      'view.prevTerminal': 'Terminal anterior',
      'view.closeTerminal': 'Cerrar terminal',
      'view.terminalSelection': 'Enviar selección de terminal al compositor',
      'view.closeTab': 'Cerrar pestaña',
      'view.reopenTab': 'Reabrir pestaña cerrada',
      'view.flipPanes': 'Cambiar el lado de la barra lateral',
      'appearance.toggleMode': 'Alternar claro / oscuro',
      'profile.default': 'Cambiar al perfil predeterminado',
      'profile.next': 'Siguiente perfil',
      'profile.prev': 'Perfil anterior',
      'profile.toggleAll': 'Alternar vista de todos los perfiles',
      'profile.create': 'Crear perfil',
      'composer.send': 'Enviar mensaje',
      'composer.newline': 'Insertar salto de línea',
      'composer.steer': 'Redirigir el turno en curso',
      'composer.queue': 'Poner mensaje en cola',
      'composer.sendQueued': 'Enviar el siguiente turno en cola',
      'composer.mention': 'Referenciar archivos, carpetas, URL',
      'composer.slash': 'Paleta de comandos con barra',
      'composer.help': 'Ayuda rápida',
      'composer.history': 'Alternar panel emergente / historial',
      'composer.cancel': 'Cerrar panel emergente · cancelar ejecución'
    }
  },

  language: {
    label: 'Idioma',
    description: 'Elige el idioma de la interfaz de escritorio.',
    saving: 'Guardando idioma…',
    saveError: 'Error al actualizar el idioma',
    switchTo: 'Cambiar idioma',
    searchPlaceholder: 'Buscar idiomas…',
    noResults: 'No se encontraron idiomas'
  },

  settings: {
    closeSettings: 'Cerrar ajustes',
    exportConfig: 'Exportar configuración',
    importConfig: 'Importar configuración',
    resetToDefaults: 'Restablecer valores predeterminados',
    resetConfirm: '¿Restablecer todos los ajustes a los valores de OpenAmer?',
    exportFailed: 'Error al exportar',
    resetFailed: 'Error al restablecer',
    nav: {
      providers: 'Proveedores',
      providerAccounts: 'Cuentas',
      providerApiKeys: 'Claves de API',
      providerCustomEndpoints: 'Endpoints personalizados',
      gateway: 'Pasarela',
      apiKeys: 'Herramientas y claves',
      keybinds: 'Atajos de teclado',
      keysTools: 'Herramientas',
      keysSettings: 'Ajustes',
      mcp: 'MCP',
      archivedChats: 'Chats archivados',
      about: 'Acerca de',
      billing: 'Facturación',
      notifications: 'Notificaciones',
      plugins: 'Plugins'
    },
    plugins: {
      title: 'Plugins de escritorio',
      blurb:
        'Extensiones de interfaz cargadas en esta aplicación — incluidas con la compilación o añadidas a la carpeta de plugins de escritorio (incluidos los que escribe OpenAmer). Desactivar descarga un plugin en vivo y sobrevive a los reinicios.',
      count: n => `${n} instalado${n === 1 ? '' : 's'}`,
      openFolder: 'Abrir carpeta de plugins',
      rescan: 'Volver a escanear',
      reveal: 'Mostrar en el gestor de archivos',
      enable: 'Activar',
      disable: 'Desactivar',
      failed: 'con error',
      empty: 'Aún no hay plugins de escritorio instalados.',
      kinds: { bundled: 'incluido', disk: 'en disco', runtime: 'en ejecución' }
    },
    notifications: {
      title: 'Notificaciones',
      intro:
        'Notificaciones nativas de escritorio, independientes de los avisos dentro de la aplicación. Son locales del dispositivo: cada equipo guarda sus propios ajustes.',
      enableAll: 'Activar notificaciones',
      enableAllDesc: 'Interruptor principal. Desactívalo para silenciar todas las notificaciones siguientes.',
      focusedHint: 'Las alertas de finalización solo se activan cuando OpenAmer está en segundo plano.',
      kinds: {
        approval: {
          label: 'Aprobación necesaria',
          description: 'Hay un comando esperando que lo apruebes o rechaces.'
        },
        input: {
          label: 'Entrada necesaria',
          description: 'OpenAmer hizo una pregunta o necesita una contraseña o un secreto.'
        },
        turnDone: {
          label: 'Respuesta lista',
          description: 'Un turno terminó mientras OpenAmer estaba en segundo plano.'
        },
        turnError: {
          label: 'El turno falló',
          description: 'Un turno terminó con un error.'
        },
        backgroundDone: {
          label: 'Tarea en segundo plano finalizada',
          description: 'Un comando de terminal en segundo plano se completó.'
        },
        credits: {
          label: 'Alertas de créditos',
          description: 'El acceso a créditos se pausó o se restauró.'
        }
      },
      test: 'Enviar notificación de prueba',
      testTitle: 'OpenAmer',
      testBody: 'Las notificaciones funcionan.',
      testSent: 'Prueba enviada. Si no aparece nada, revisa los permisos de notificación del sistema y el modo No molestar.',
      testUnsupported: 'Este sistema no admite notificaciones nativas.',
      completionSoundTitle: 'Sonido de finalización',
      completionSoundDesc: 'Suena cuando termina un turno del agente. Elige un preset y pruébalo aquí.',
      completionSoundPreview: 'Probar'
    },
    sections: {
      model: 'Modelo',
      chat: 'Chat',
      appearance: 'Apariencia',
      workspace: 'Espacio de trabajo',
      safety: 'Seguridad',
      memory: 'Memoria y contexto',
      voice: 'Voz',
      advanced: 'Avanzado'
    },
    searchPlaceholder: {
      about: 'Acerca de OpenAmer Desktop',
      config: 'Buscar ajustes…',
      gateway: 'Conexión de la pasarela…',
      keys: 'Buscar claves de API…',
      mcp: 'Buscar servidores MCP…',
      sessions: 'Buscar sesiones archivadas…'
    },
    modeOptions: {
      light: { label: 'Claro', description: 'Superficies de escritorio luminosas' },
      dark: { label: 'Oscuro', description: 'Espacio de trabajo con bajo deslumbramiento' },
      system: { label: 'Sistema', description: 'Seguir la apariencia del sistema operativo' }
    },
    appearance: {
      title: 'Apariencia',
      intro:
        'Estas son preferencias de visualización solo de escritorio. El modo controla el brillo; el tema controla la paleta de acentos y el estilo del chat.',
      colorMode: 'Modo de color',
      colorModeDesc: 'Elige un modo fijo o deja que OpenAmer siga la configuración de tu sistema.',
      toolViewTitle: 'Visualización de llamadas a herramientas',
      toolViewDesc: 'Producto oculta los datos crudos de las herramientas; Técnico muestra la entrada/salida completa.',
      uiScaleTitle: 'Escala de la interfaz',
      uiScaleDesc: (percent: number) =>
        `Escala el texto y los controles de toda la aplicación. También funcionan Cmd/Ctrl con +, - y 0. Actual: ${percent}%.`,
      translucencyTitle: 'Translucidez de la ventana',
      translucencyDesc: 'Ve tu escritorio a través de toda la ventana. Solo en macOS y Windows.',
      backdropTitle: 'Fondo del chat',
      backdropDesc: 'La tenue imagen de estatua detrás de la conversación.',
      embedsTitle: 'Contenidos incrustados',
      embedsDesc:
        'Las vistas previas se cargan desde sitios de terceros (YouTube, X, …). Preguntar muestra un marcador hasta que permitas cada uno; Siempre los carga automáticamente; Desactivado mantiene enlaces simples.',
      embedsAsk: 'Preguntar',
      embedsAlways: 'Siempre',
      embedsOff: 'Desactivado',
      product: 'Producto',
      productDesc: 'Actividad de herramientas amigable con resúmenes concisos.',
      technical: 'Técnico',
      technicalDesc: 'Incluye argumentos/resultados crudos y detalles de bajo nivel.',
      themeTitle: 'Tema',
      themeDesc: 'Solo paletas de escritorio. El modo seleccionado se aplica encima.',
      themeProfileNote: profile => `Guardado para el perfil ${profile} — cada perfil conserva su propio tema.`,
      installTitle: 'Instalar desde VS Code',
      installDesc:
        'Pega un id de extensión del Marketplace (p. ej. dracula-theme.theme-dracula) para convertir su tema de color en una paleta de escritorio.',
      installPlaceholder: 'publisher.extension',
      installButton: 'Instalar',
      installing: 'Instalando…',
      installError: 'No se pudo instalar ese tema.',
      installed: name => `Se instaló “${name}”.`,
      removeTheme: 'Quitar tema',
      importedBadge: 'Importado'
    }
  }
})
