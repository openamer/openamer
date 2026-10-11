// install-home.ts
//
// Resolve the home that belongs to THIS install, from the install itself.
//
// Why this exists: OPENAMER_HOME is not install-scoped. install.ps1 writes it to
// the *user* environment, so on a box with two install trees it names whichever
// tree wrote it last, and every later process inherits that spelling. The
// desktop used to read process env -> registry -> %LOCALAPPDATA%\openamer, so
// when the shared value was wrong (or absent and a fallback had been persisted)
// the app booted against an empty home: a ~51-byte onboarding stub beside a real
// 13 KB config.yaml, backend "ready", everything empty.
//
// The ladder below is the desktop's rung for that, and it is deliberately the
// same ordered ladder as the two other surfaces that can answer this question --
// keep the three in lockstep:
//
//   scripts/install.ps1 Resolve-OpenAmerHome             (installer)
//   openamer_constants.get_install_scoped_openamer_home   (CLI, dep bootstrap)
//   this file                                            (desktop)
//
// Nothing here guesses: an install that cannot produce evidence yields null, and
// the caller keeps its previous override order (process env -> sandbox ->
// registry -> platform default) untouched.

import fs from 'node:fs'
import path from 'node:path'

const DEFAULT_MAX_DEPTH = 6

// Injection seams so the ladder can be driven with fakes (and with the real fs
// in tests) without touching the module-level bindings.
const defaultDeps = {
  isFile: (p: string) => {
    try {
      return fs.statSync(p).isFile()
    } catch {
      return false
    }
  },
  isDirectory: (p: string) => {
    try {
      return fs.statSync(p).isDirectory()
    } catch {
      return false
    }
  },
  readTextFile: (p: string) => {
    try {
      return fs.readFileSync(p, 'utf8')
    } catch {
      return null
    }
  },
  pathModule: path
}

// The breadcrumb install.ps1 writes beside the checkout once a home is proven
// (Set-InstallHomeBreadcrumb). BOM-less UTF-8, so no BOM to strip; a stray one is
// trimmed anyway. A relative or empty value is rejected rather than resolved
// against the cwd -- the writer only ever emits an absolute path, so anything
// else is corruption, and guessing at it is what we are here to stop.
function homeFromInstallBreadcrumb(checkoutDir, deps = {}) {
  const { isFile, readTextFile, pathModule } = { ...defaultDeps, ...deps }

  if (!checkoutDir) {
    return null
  }

  const recorded = readTextFile(pathModule.join(checkoutDir, '.openamer-home'))

  if (!recorded) {
    return null
  }

  const home = String(recorded)
    .replace(/^\uFEFF/, '')
    .trim()

  if (!home || !pathModule.isAbsolute(home)) {
    return null
  }

  return home
}

// Shipped layout: <home>/openamer-agent. The parent is only trusted when the
// checkout carries install evidence (.git), so a bare dev checkout cannot invent
// a home out of its own name.
function homeFromShippedLayout(checkoutDir, deps = {}) {
  const { isDirectory, pathModule } = { ...defaultDeps, ...deps }

  if (!checkoutDir) {
    return null
  }

  const resolved = pathModule.resolve(checkoutDir)

  if (pathModule.basename(resolved).toLowerCase() !== 'openamer-agent') {
    return null
  }

  if (!isDirectory(pathModule.join(resolved, '.git'))) {
    return null
  }

  return pathModule.dirname(resolved)
}

// Candidate checkouts, most specific first: each seed path itself, then its
// ancestors up to maxDepth. The desktop binary lives inside the install
// (`<home>/openamer-agent/apps/desktop/release/win-unpacked/OpenAmer.exe`), so
// walking up from execPath/appRoot is how the *launched* install names itself
// without needing OPENAMER_HOME to be right first.
function installHomeCandidatesFromPaths(seedPaths, deps = {}) {
  const { isDirectory, pathModule, maxDepth = DEFAULT_MAX_DEPTH } = { ...defaultDeps, ...deps }
  const seen = new Set()
  const candidates = []

  const push = candidate => {
    if (!candidate) {
      return
    }

    const resolved = pathModule.resolve(candidate)
    const key = resolved.toLowerCase()

    if (seen.has(key)) {
      return
    }

    seen.add(key)
    candidates.push(resolved)
  }

  for (const seed of seedPaths || []) {
    if (!seed) {
      continue
    }

    let current = pathModule.resolve(seed)

    // A seed pointing at a file (execPath) starts from its directory.
    if (!isDirectory(current)) {
      current = pathModule.dirname(current)
    }

    for (let depth = 0; depth <= maxDepth; depth += 1) {
      push(current)

      const parent = pathModule.dirname(current)

      if (parent === current) {
        break
      }

      current = parent
    }
  }

  return candidates
}

// First candidate that can name its own home wins.
// Returns { home, source, checkout } or null.
function resolveInstallScopedOpenAmerHome(candidates, deps = {}) {
  for (const candidate of candidates || []) {
    const fromBreadcrumb = homeFromInstallBreadcrumb(candidate, deps)

    if (fromBreadcrumb) {
      return { home: fromBreadcrumb, source: 'breadcrumb', checkout: candidate }
    }

    const fromLayout = homeFromShippedLayout(candidate, deps)

    if (fromLayout) {
      return { home: fromLayout, source: 'shipped-layout', checkout: candidate }
    }
  }

  return null
}

export {
  homeFromInstallBreadcrumb,
  homeFromShippedLayout,
  installHomeCandidatesFromPaths,
  resolveInstallScopedOpenAmerHome
}
