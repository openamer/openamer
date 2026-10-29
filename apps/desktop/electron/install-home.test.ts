import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { test } from 'vitest'

import {
  homeFromInstallBreadcrumb,
  homeFromShippedLayout,
  installHomeCandidatesFromPaths,
  resolveInstallScopedOpenAmerHome
} from './install-home'

// The fake-driven cases are written against POSIX paths and say so explicitly
// (pathModule: path.posix) -- the module defaults to the native module, so a
// POSIX fixture under the Windows default would be drive-qualified into
// C:\opt\... and test nothing.
const P = path.posix

function fakeFs({ files = {}, directories = [] } = {}) {
  return {
    isFile: p => Object.prototype.hasOwnProperty.call(files, p),
    isDirectory: p => directories.includes(p),
    readTextFile: p => (Object.prototype.hasOwnProperty.call(files, p) ? files[p] : null),
    pathModule: P
  }
}

test('breadcrumb beside the checkout names the install home', () => {
  const checkout = '/opt/openamer-laptop/openamer-agent'
  const home = '/opt/openamer-laptop'
  const deps = fakeFs({ files: { [P.join(checkout, '.openamer-home')]: home } })

  assert.equal(homeFromInstallBreadcrumb(checkout, deps), home)
  assert.equal(resolveInstallScopedOpenAmerHome([checkout], deps).home, home)
  assert.equal(resolveInstallScopedOpenAmerHome([checkout], deps).source, 'breadcrumb')
})

test('a BOM left on the breadcrumb is stripped, not glued onto the path', () => {
  const checkout = '/opt/openamer-laptop/openamer-agent'

  const deps = fakeFs({
    files: { [P.join(checkout, '.openamer-home')]: '\uFEFF/opt/openamer-laptop\n' }
  })

  assert.equal(homeFromInstallBreadcrumb(checkout, deps), '/opt/openamer-laptop')
})

test('an empty or relative breadcrumb is refused rather than resolved', () => {
  const checkout = '/opt/openamer'
  const markerPath = P.join(checkout, '.openamer-home')

  assert.equal(homeFromInstallBreadcrumb(checkout, fakeFs({ files: { [markerPath]: '   ' } })), null)
  assert.equal(homeFromInstallBreadcrumb(checkout, fakeFs({ files: { [markerPath]: 'relative/home' } })), null)
  assert.equal(homeFromInstallBreadcrumb(checkout, fakeFs()), null)
})

test('shipped layout derives the parent only with install evidence', () => {
  const root = '/opt/openamer-laptop/openamer-agent'

  assert.equal(homeFromShippedLayout(root, fakeFs({ directories: [P.join(root, '.git')] })), '/opt/openamer-laptop')
  // Same name, no .git: a dev checkout must not invent a home out of its name.
  assert.equal(homeFromShippedLayout(root, fakeFs()), null)
  // Install evidence, wrong basename: not the shipped layout.
  assert.equal(homeFromShippedLayout('/opt/work/openamer', fakeFs({ directories: ['/opt/work/openamer/.git'] })), null)
})

test('the breadcrumb outranks the shipped layout and every later rung', () => {
  const home = '/opt/openamer-laptop'
  const root = P.join(home, 'openamer-agent')
  const elsewhere = '/opt/other-tree'

  const deps = fakeFs({
    files: { [P.join(root, '.openamer-home')]: elsewhere },
    directories: [P.join(root, '.git')]
  })

  const resolved = resolveInstallScopedOpenAmerHome([root], deps)

  assert.equal(resolved.home, elsewhere)
  assert.equal(resolved.source, 'breadcrumb')
})

test('an install with no evidence resolves to null so the caller keeps its own order', () => {
  assert.equal(resolveInstallScopedOpenAmerHome(['/opt/work/openamer', '/opt'], fakeFs()), null)
  assert.equal(resolveInstallScopedOpenAmerHome([], fakeFs()), null)
})

test('candidate walk is bounded and dedupes overlapping seeds', () => {
  const candidates = installHomeCandidatesFromPaths(['/a/b/c', '/a/b'], {
    isDirectory: p => p === '/a/b/c',
    maxDepth: 2,
    pathModule: P
  })

  assert.deepEqual(candidates, ['/a/b/c', '/a/b', '/a', '/'])
})

test('candidate walk finds the install from the packaged binary inside it', () => {
  // Real fs, real ancestor walk, real reader: this is the shape that failed in
  // the wild -- `<home>/openamer-agent/apps/desktop/release/win-unpacked/
  // OpenAmer.exe` booting against an empty home because nothing consulted the
  // install it lived in.
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'oa-install-home-'))
  const checkout = path.join(home, 'openamer-agent')
  const exeDir = path.join(checkout, 'apps', 'desktop', 'release', 'win-unpacked')
  const exe = path.join(exeDir, 'OpenAmer.exe')

  fs.mkdirSync(path.join(checkout, '.git'), { recursive: true })
  fs.mkdirSync(exeDir, { recursive: true })
  fs.writeFileSync(exe, '')

  try {
    const candidates = installHomeCandidatesFromPaths([exe])

    assert.ok(candidates.includes(checkout), `walk must reach the checkout: ${JSON.stringify(candidates)}`)
    assert.ok(candidates.length <= 7, 'walk stays bounded')

    const resolved = resolveInstallScopedOpenAmerHome(candidates)

    assert.equal(resolved.home, home)
    assert.equal(resolved.source, 'shipped-layout')

    // ...and the breadcrumb install.ps1 writes (BOM-less UTF-8) is read back
    // verbatim. This is the exact byte shape Set-InstallHomeBreadcrumb emits.
    fs.writeFileSync(path.join(checkout, '.openamer-home'), home, { encoding: 'utf8' })

    const fromBreadcrumb = resolveInstallScopedOpenAmerHome(candidates)

    assert.equal(fromBreadcrumb.home, home)
    assert.equal(fromBreadcrumb.source, 'breadcrumb')

    // A BOM, if one ever appears, must not be glued onto the path.
    fs.writeFileSync(path.join(checkout, '.openamer-home'), `\uFEFF${home}\n`, { encoding: 'utf8' })

    assert.equal(resolveInstallScopedOpenAmerHome(candidates).home, home)
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
})
