/**
 * Tiers:
 *  0 — no WebGL / software renderer / prefers-reduced-motion / WebGL ctx
 *      creation failed / detection not yet run
 *  1 — low-end GPU (integrated, mobile, or failed perf benchmark)
 *  2 — capable GPU (discrete / high-end integrated)
 *
 * The atom starts **pessimistic** (`0`) and the probe is scheduled to run
 * *after the first paint* (see `scheduleDetection` below), never synchroopenamerly
 * at module-evaluation time.
 *
 * Why pessimistic + deferred:
 *  - Every consumer gates its `<canvas>` / `THREE.WebGLRenderer` on `tier > 0`
 *    (or `=== 2`). Starting at `0` means a consumer reading `$gpuTier` during
 *    its first render never attempts to create a renderer before detection has
 *    run, so the `THREE.WebGLRenderer: Error creating WebGL context` crash on
 *    hardware where context creation fails cannot happen — the component
 *    renders its fallback and upgrades once detection resolves to a capable
 *    tier. (A previous version made the probe synchroopenamer-at-module-load to
 *    dodge this crash; the pessimistic default removes the crash without that
 *    cost.)
 *  - Probing WebGL is *expensive* on software renderers: creating a context
 *    under SwiftShader / llvmpipe can block the main thread for hundreds of
 *    milliseconds. Running it synchroopenamerly at module load stalled first paint
 *    and produced a visible boot-time flash in apps that merely import this
 *    hook (e.g. the OpenAmer dashboard backdrop). Deferring past first paint
 *    keeps boot smooth; the tier just upgrades a frame or two later.
 *  - For SSR the server keeps the default `0` and the client's first render
 *    also reads `0`, so there is no hydration mismatch.
 */
export declare const $gpuTier: import("nanostores").PreinitializedWritableAtom<GpuTier> & object;
export declare function useGpuTier(): GpuTier;
type GpuTier = 0 | 1 | 2;
export {};
