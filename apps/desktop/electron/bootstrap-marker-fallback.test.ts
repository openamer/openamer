/**
 * Tests for electron/bootstrap-marker-fallback.ts.
 *
 * Run with: node --test electron/bootstrap-marker-fallback.test.ts
 * (Wired into npm test:desktop:platforms in package.json.)
 *
 * These are BEHAVIOUR CONTRACTS, not change detectors: the invariant is
 * "a missing marker never sends a demonstrably working, user-confirmed
 * install back through the installer", not "the function returns X for
 * input Y".
 */

import assert from 'node:assert/strict'

import { test } from 'vitest'

import {
  decideBootstrapMarkerFallback,
  mayTrustRuntimeWithoutMarker
} from './bootstrap-marker-fallback'

test('a valid marker is trusted', () => {
  const decision = decideBootstrapMarkerFallback({
    markerPresent: true,
    runtimeUsable: true,
    localBootstrapConfirmed: false
  })

  assert.equal(decision, 'marker-present')
  assert.equal(mayTrustRuntimeWithoutMarker(decision), true)
})

test('a missing marker over a working, confirmed install does NOT re-run the installer', () => {
  // This is the regression: the install runs fine, the user confirmed it, but
  // the marker was lost. The installer must not be re-run.
  const decision = decideBootstrapMarkerFallback({
    markerPresent: false,
    runtimeUsable: true,
    localBootstrapConfirmed: true
  })

  assert.equal(decision, 'runtime-usable')
  assert.equal(mayTrustRuntimeWithoutMarker(decision), true)
})

test('a missing marker on a genuinely broken install still triggers the installer', () => {
  const decision = decideBootstrapMarkerFallback({
    markerPresent: false,
    runtimeUsable: false,
    localBootstrapConfirmed: true
  })

  assert.equal(decision, 'runtime-unusable')
  assert.equal(mayTrustRuntimeWithoutMarker(decision), false)
})

test('a missing marker before the user confirmed is a first run, not a repair', () => {
  // The first-run setup UI must still be shown -- we may not silently skip
  // the user's first-run choice just because the runtime happens to import.
  const decision = decideBootstrapMarkerFallback({
    markerPresent: false,
    runtimeUsable: true,
    localBootstrapConfirmed: false
  })

  assert.equal(decision, 'runtime-unusable')
  assert.equal(mayTrustRuntimeWithoutMarker(decision), false)
})

test('an explicit repair request overrides a working runtime', () => {
  // The "repair" IPC deletes the marker on purpose to force a full reinstall.
  // That intent must survive: we must not short-circuit it.
  const decision = decideBootstrapMarkerFallback({
    markerPresent: false,
    runtimeUsable: true,
    localBootstrapConfirmed: true,
    repairRequested: true
  })

  assert.equal(decision, 'repair-requested')
  assert.equal(mayTrustRuntimeWithoutMarker(decision), false)
})

test('an explicit repair request overrides even a present marker', () => {
  const decision = decideBootstrapMarkerFallback({
    markerPresent: true,
    runtimeUsable: true,
    localBootstrapConfirmed: true,
    repairRequested: true
  })

  assert.equal(decision, 'repair-requested')
  assert.equal(mayTrustRuntimeWithoutMarker(decision), false)
})
