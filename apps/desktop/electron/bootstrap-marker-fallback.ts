/**
 * bootstrap-marker-fallback.ts
 *
 * Decide whether an install that is missing its bootstrap-complete marker
 * should still be trusted as "already installed".
 *
 * Background (measured on Windows, 2026-10-25):
 *   The desktop resolver walks a ladder of candidates. Step 3 accepts
 *   ACTIVE_OPENAMER_ROOT only when the bootstrap-complete marker is present
 *   AND current-schema. When the marker is missing but the install is
 *   perfectly runnable, the resolver fell through to step 6 and returned the
 *   "bootstrap-needed" sentinel. The desktop then handed the recovery to
 *   openamer-setup.exe, which failed to update (git error), and the whole
 *   thing restarted -- five restarts in four minutes, an infinite recovery
 *   loop over a fully working install.
 *
 *   The marker is an ATTESTATION, not the source of truth. The install itself
 *   is the source of truth. A marker can be missing for reasons that have
 *   nothing to do with the install being broken:
 *     - the marker was never written (CLI-only install, or a first-launch
 *       bootstrap that completed the install but was interrupted before the
 *       write),
 *     - the marker was deleted by the "repair" IPC path,
 *     - the marker was lost during an update that rewrote the install tree.
 *
 * The rule this module encodes:
 *   A missing marker is only fatal while the user has NOT yet confirmed a
 *   local install. Once the runtime is demonstrably usable, a missing marker
 *   is a bookkeeping gap, not a broken install -- and repairing it must not
 *   send the user through the installer again.
 *
 * The "repair" IPC path deliberately deletes the marker to force a full
 * re-install of a genuinely broken venv. That intent is preserved: repair
 * sets an explicit flag, and this module reports "repair requested" so the
 * caller can honour it instead of silently trusting the runtime.
 */

/** Why we are asking, and what the caller wants to do about it. */
export type BootstrapMarkerFallbackDecision =
  /** The marker is present and valid. Trust it. */
  | 'marker-present'
  /** No marker, but the runtime is usable and the user already confirmed. Trust the runtime. */
  | 'runtime-usable'
  /** No marker and the runtime is NOT usable. The install really is missing/broken. */
  | 'runtime-unusable'
  /** The user explicitly asked for a repair. Re-run the installer regardless. */
  | 'repair-requested'

export interface BootstrapMarkerFallbackOptions {
  /** True when the bootstrap-complete marker file exists and parses. */
  markerPresent: boolean
  /** True when the canonical install can actually run the CLI right now. */
  runtimeUsable: boolean
  /** True when the user has already confirmed a local install in this session. */
  localBootstrapConfirmed: boolean
  /** True when the user explicitly triggered the "repair" flow. */
  repairRequested?: boolean
}

/**
 * Pure decision function. Exported separately from the Electron runtime so it
 * can be unit-tested without dragging in electron.
 */
export function decideBootstrapMarkerFallback({
  markerPresent,
  runtimeUsable,
  localBootstrapConfirmed,
  repairRequested = false
}: BootstrapMarkerFallbackOptions): BootstrapMarkerFallbackDecision {
  // An explicit repair always wins: the user asked for the installer to run
  // again, so we must not short-circuit it with a "looks fine to me".
  if (repairRequested) {
    return 'repair-requested'
  }

  if (markerPresent) {
    return 'marker-present'
  }

  // No marker. The install is only trustworthy if the runtime actually works
  // AND the user has already confirmed a local install -- otherwise this is
  // the genuine first-run case, and the first-run setup UI must be shown.
  if (runtimeUsable && localBootstrapConfirmed) {
    return 'runtime-usable'
  }

  // The runtime is unusable: the install really is missing or broken, and the
  // installer must run. This includes "runtime usable but the user never
  // confirmed" -- that is first-run, not a repair.
  return 'runtime-unusable'
}

/**
 * True when the resolver may treat the install as present even though the
 * bootstrap-complete marker is missing.
 */
export function mayTrustRuntimeWithoutMarker(decision: BootstrapMarkerFallbackDecision): boolean {
  return decision === 'marker-present' || decision === 'runtime-usable'
}
