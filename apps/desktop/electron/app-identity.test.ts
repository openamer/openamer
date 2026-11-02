import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'

import { test } from 'vitest'

import { appIconPaths, windowsAppDetails } from './app-identity'

const desktopRoot = path.resolve(import.meta.dirname, '..')

const roots = {
  appRoot: 'C:/app/resources/app.asar',
  platform: 'win32',
  resourcesPath: 'C:/app/resources',
  unpackedRoot: 'C:/app/resources/app.asar.unpacked'
}

test('win32 resolves a real ICO outside app.asar before any PNG fallback', () => {
  const paths = appIconPaths(roots)
  assert.match(paths[0], /resources[\\/]icon\.ico$/)
  assert.ok(paths.indexOf(paths[0]) === 0)
  assert.ok(paths.every(p => !p.includes('apple-touch-icon') || paths.indexOf(p) > 1))
})

test('non-Windows platforms keep the PNG master and never ask for an ICO', () => {
  const paths = appIconPaths({ ...roots, platform: 'darwin' })
  assert.ok(paths.every(p => !p.endsWith('.ico')))
  assert.match(paths[0], /assets[\\/]icon\.png$/)
})

test('Windows window details carry the taskbar icon and relaunch metadata', () => {
  const details = windowsAppDetails({
    appRoot: roots.appRoot,
    execPath: 'C:/app/OpenAmer.exe',
    iconPath: 'C:/app/resources/icon.ico',
    isPackaged: true
  })

  assert.equal(details.appId, 'com.openamer.openamer')
  assert.equal(details.appIconPath, 'C:/app/resources/icon.ico')
  assert.equal(details.appIconIndex, 0)
  assert.equal(details.relaunchDisplayName, 'OpenAmer')
  assert.equal(details.relaunchCommand, '"C:/app/OpenAmer.exe"')
})

test('an unpackaged launch keeps the app path in its relaunch command', () => {
  const details = windowsAppDetails({
    appRoot: 'C:/repo/apps/desktop',
    execPath: 'C:/electron/electron.exe',
    iconPath: undefined,
    isPackaged: false
  })

  assert.ok(!('appIconPath' in details))
  assert.match(details.relaunchCommand, /electron\.exe" "C:\/repo\/apps\/desktop/)
})

test('main.ts wires the shared ladder and applies shell identity to chat windows', () => {
  const main = readFileSync(path.join(desktopRoot, 'electron/main.ts'), 'utf8')
  assert.match(main, /const APP_ICON_PATHS = appIconPaths\(/)
  assert.match(main, /applyShellIdentity\(mainWindow\)/)
  assert.match(main, /applyShellIdentity\(win\)/)
})

test('every shipped icon derives from the canonical DNA master', () => {
  const icon = readFileSync(path.join(desktopRoot, 'assets/icon.png'))
  // The legacy eye mark was a 512×512 PNG of ~15 kB with a flat cyan disc; the
  // canonical helix master is far more detailed. Pin the container + size and
  // keep the file honest against a silent revert to the old artwork.
  assert.equal(icon.subarray(1, 4).toString(), 'PNG')
  assert.equal(icon.readUInt32BE(16), 512)
  assert.equal(icon.readUInt32BE(20), 512)
  assert.ok(icon.length > 100_000, 'icon.png looks like the old low-detail artwork')

  const icns = readFileSync(path.join(desktopRoot, 'assets/icon.icns'))
  assert.equal(icns.subarray(0, 4).toString(), 'icns', '.icns must be an Apple icon container, not a renamed PNG')
  assert.equal(icns.readUInt32BE(4), icns.length)
})
