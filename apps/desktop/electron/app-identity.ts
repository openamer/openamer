import path from 'node:path'

/** Prefer a real external ICO for the Windows shell, not an Apple touch icon
 * inside app.asar. Keep unpacked/source fallbacks for development builds. */
export function appIconPaths({ appRoot, unpackedRoot, resourcesPath, platform }: {
  appRoot: string
  unpackedRoot: string
  resourcesPath: string
  platform: string
}) {
  return [
    ...(platform === 'win32' ? [
      path.join(resourcesPath, 'icon.ico'),
      path.join(appRoot, 'assets', 'icon.ico'),
      path.join(unpackedRoot, 'assets', 'icon.ico')
    ] : []),
    path.join(appRoot, 'assets', 'icon.png'),
    path.join(unpackedRoot, 'assets', 'icon.png'),
    path.join(appRoot, 'public', 'apple-touch-icon.png'),
    path.join(appRoot, 'dist', 'apple-touch-icon.png'),
    path.join(unpackedRoot, 'dist', 'apple-touch-icon.png')
  ]
}

/** Window-level shell metadata is needed for uninstalled/source launches too:
 * the global AppUserModelID alone does not provide a relaunch icon resource. */
export function windowsAppDetails({ iconPath, execPath, appRoot, isPackaged }: {
  iconPath: string | undefined
  execPath: string
  appRoot: string
  isPackaged: boolean
}) {
  return {
    appId: 'com.openamer.openamer',
    ...(iconPath ? { appIconPath: iconPath, appIconIndex: 0 } : {}),
    relaunchCommand: isPackaged ? `"${execPath}"` : `"${execPath}" "${appRoot}"`,
    relaunchDisplayName: 'OpenAmer'
  }
}
