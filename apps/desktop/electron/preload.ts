import { contextBridge, ipcRenderer, webUtils } from 'electron'

contextBridge.exposeInMainWorld('openamerDesktop', {
  getConnection: profile => ipcRenderer.invoke('openamer:connection', profile),
  revalidateConnection: () => ipcRenderer.invoke('openamer:connection:revalidate'),
  touchBackend: profile => ipcRenderer.invoke('openamer:backend:touch', profile),
  getGatewayWsUrl: profile => ipcRenderer.invoke('openamer:gateway:ws-url', profile),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('openamer:window:openSession', sessionId, opts),
  openWindow: () => ipcRenderer.invoke('openamer:window:openInstance'),
  claimAmbientCue: key => ipcRenderer.invoke('openamer:ambient:claim', key),
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('openamer:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('openamer:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('openamer:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('openamer:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('openamer:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('openamer:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('openamer:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('openamer:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('openamer:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('openamer:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('openamer:pet-overlay:control', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('openamer:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('openamer:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('openamer:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('openamer:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('openamer:connection-config:test', payload),
  sshConfigHosts: () => ipcRenderer.invoke('openamer:ssh-config:hosts'),
  sshResolveHost: host => ipcRenderer.invoke('openamer:ssh-config:resolve', host),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('openamer:connection-config:probe', remoteUrl),
  oauthLoginConnectionConfig: remoteUrl => ipcRenderer.invoke('openamer:connection-config:oauth-login', remoteUrl),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('openamer:connection-config:oauth-logout', remoteUrl),
  // OpenAmer Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('openamer:cloud:status'),
    login: () => ipcRenderer.invoke('openamer:cloud:login'),
    logout: () => ipcRenderer.invoke('openamer:cloud:logout'),
    discover: org => ipcRenderer.invoke('openamer:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('openamer:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    get: () => ipcRenderer.invoke('openamer:profile:get'),
    set: name => ipcRenderer.invoke('openamer:profile:set', name)
  },
  api: request => ipcRenderer.invoke('openamer:api', request),
  notify: payload => ipcRenderer.invoke('openamer:notify', payload),
  requestMicrophoneAccess: () => ipcRenderer.invoke('openamer:requestMicrophoneAccess'),
  readFileDataUrl: filePath => ipcRenderer.invoke('openamer:readFileDataUrl', filePath),
  readFileText: filePath => ipcRenderer.invoke('openamer:readFileText', filePath),
  selectPaths: options => ipcRenderer.invoke('openamer:selectPaths', options),
  writeClipboard: text => ipcRenderer.invoke('openamer:writeClipboard', text),
  saveImageFromUrl: url => ipcRenderer.invoke('openamer:saveImageFromUrl', url),
  saveImageBuffer: (data, ext) => ipcRenderer.invoke('openamer:saveImageBuffer', { data, ext }),
  saveClipboardImage: () => ipcRenderer.invoke('openamer:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('openamer:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('openamer:watchPreviewFile', url),
  stopPreviewFileWatch: id => ipcRenderer.invoke('openamer:stopPreviewFileWatch', id),
  setTitleBarTheme: payload => ipcRenderer.send('openamer:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('openamer:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('openamer:translucency', payload),
  setKeepAwake: on => ipcRenderer.send('openamer:keep-awake', on),
  setPreviewShortcutActive: active => ipcRenderer.send('openamer:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('openamer:openExternal', url),
  openPreviewInBrowser: url => ipcRenderer.invoke('openamer:openPreviewInBrowser', url),
  fetchLinkTitle: url => ipcRenderer.invoke('openamer:fetchLinkTitle', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('openamer:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('openamer:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('openamer:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('openamer:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('openamer:zoom:get'),
    setPercent: percent => ipcRenderer.send('openamer:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('openamer:zoom:changed', listener)

      return () => ipcRenderer.removeListener('openamer:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('openamer:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('openamer:logs:recent'),
  readDir: dirPath => ipcRenderer.invoke('openamer:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('openamer:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('openamer:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('openamer:fs:openDir', dirPath),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('openamer:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('openamer:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('openamer:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('openamer:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('openamer:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('openamer:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('openamer:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('openamer:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('openamer:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('openamer:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('openamer:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('openamer:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('openamer:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('openamer:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('openamer:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('openamer:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('openamer:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('openamer:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('openamer:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('openamer:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('openamer:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('openamer:git:review:shipInfo', repoPath),
      createPr: repoPath => ipcRenderer.invoke('openamer:git:review:createPr', repoPath)
    }
  },
  terminal: {
    cwd: id => ipcRenderer.invoke('openamer:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('openamer:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('openamer:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('openamer:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('openamer:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `openamer:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `openamer:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('openamer:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('openamer:close-preview-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('openamer:open-updates', listener)

    return () => ipcRenderer.removeListener('openamer:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('openamer:deep-link', listener)

    return () => ipcRenderer.removeListener('openamer:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('openamer:deep-link-ready'),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('openamer:window-state-changed', listener)

    return () => ipcRenderer.removeListener('openamer:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('openamer:focus-session', listener)

    return () => ipcRenderer.removeListener('openamer:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('openamer:notification-action', listener)

    return () => ipcRenderer.removeListener('openamer:notification-action', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('openamer:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('openamer:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('openamer:backend-exit', listener)

    return () => ipcRenderer.removeListener('openamer:backend-exit', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('openamer:connection:applied', listener)

    return () => ipcRenderer.removeListener('openamer:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('openamer:power-resume', listener)

    return () => ipcRenderer.removeListener('openamer:power-resume', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('openamer:boot-progress', listener)

    return () => ipcRenderer.removeListener('openamer:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('openamer:bootstrap:get'),
  continueBootstrapLocal: () => ipcRenderer.invoke('openamer:bootstrap:continue-local'),
  resetBootstrap: () => ipcRenderer.invoke('openamer:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('openamer:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('openamer:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('openamer:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('openamer:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('openamer:version'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('openamer:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('openamer:uninstall:summary'),
    run: mode => ipcRenderer.invoke('openamer:uninstall:run', { mode })
  },
  updates: {
    check: () => ipcRenderer.invoke('openamer:updates:check'),
    apply: opts => ipcRenderer.invoke('openamer:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('openamer:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('openamer:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('openamer:updates:progress', listener)

      return () => ipcRenderer.removeListener('openamer:updates:progress', listener)
    }
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('openamer:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('openamer:vscode-theme:search', query)
  }
})
