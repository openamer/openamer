'use client'

import { useStore } from '@nanostores/react'
import { atom } from 'nanostores'

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
export const $gpuTier = atom<GpuTier>(0)

const SOFTWARE_PATTERNS =
  /swiftshader|llvmpipe|softpipe|software|microsoft basic/i

const LOW_END_PATTERNS =
  /intel.*hd|intel.*uhd|intel.*iris|mali|adreno\s?[1-5]|powervr|apple gpu/i

let detected = false

function detectGpuTier() {
  if (detected || typeof window === 'undefined') {
    return
  }

  detected = true

  // The atom already holds 0; the early returns below simply leave it there.
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return
  }

  let gl: null | WebGLRenderingContext = null

  try {
    const canvas = document.createElement('canvas')
    gl = (canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl')) as null | WebGLRenderingContext
  } catch {
    // Some sandboxed / hardened contexts throw on getContext rather than
    // returning null (e.g. certain corporate browser policies). Treat as
    // "no WebGL available".
    return
  }

  if (!gl) {
    return
  }

  const ext = gl.getExtension('WEBGL_debug_renderer_info')
  const renderer = String(
    ext
      ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)
      : gl.getParameter(gl.RENDERER)
  )

  if (SOFTWARE_PATTERNS.test(renderer)) {
    gl.getExtension('WEBGL_lose_context')?.loseContext()

    return
  }

  if (LOW_END_PATTERNS.test(renderer)) {
    $gpuTier.set(1)
    gl.getExtension('WEBGL_lose_context')?.loseContext()

    return
  }

  $gpuTier.set(2)

  runBenchmark(gl)
    .then(fps => $gpuTier.set(fps < 30 ? 1 : 2))
    .catch(() => $gpuTier.set(1))
    .finally(() => gl?.getExtension('WEBGL_lose_context')?.loseContext())
}

/**
 * Run detection once, *after* the first paint so the (potentially expensive)
 * WebGL probe never blocks initial render. Prefer `requestIdleCallback` so the
 * probe yields to rendering and input; fall back to a double
 * `requestAnimationFrame` (guarantees at least one painted frame) and finally
 * `setTimeout` where neither exists.
 */
function scheduleDetection() {
  if (typeof window === 'undefined') {
    return
  }

  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(() => detectGpuTier(), { timeout: 1000 })
  } else if (typeof window.requestAnimationFrame === 'function') {
    window.requestAnimationFrame(() =>
      window.requestAnimationFrame(() => detectGpuTier())
    )
  } else {
    setTimeout(() => detectGpuTier(), 0)
  }
}

scheduleDetection()

function runBenchmark(gl: WebGLRenderingContext): Promise<number> {
  return new Promise(resolve => {
    const vs = gl.createShader(gl.VERTEX_SHADER)!
    const fs = gl.createShader(gl.FRAGMENT_SHADER)!
    gl.shaderSource(
      vs,
      'attribute vec2 a;void main(){gl_Position=vec4(a,0,1);}'
    )
    gl.shaderSource(
      fs,
      'precision highp float;uniform float t;void main(){float v=0.;for(int i=0;i<64;i++)v+=sin(float(i)*t*.01);gl_FragColor=vec4(v*.001);}'
    )
    gl.compileShader(vs)
    gl.compileShader(fs)

    const prog = gl.createProgram()!
    gl.attachShader(prog, vs)
    gl.attachShader(prog, fs)
    gl.linkProgram(prog)
    gl.useProgram(prog)

    const buf = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buf)
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
      gl.STATIC_DRAW
    )
    const a = gl.getAttribLocation(prog, 'a')
    gl.enableVertexAttribArray(a)
    gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0)

    const uT = gl.getUniformLocation(prog, 't')
    let frames = 0
    const start = performance.now()

    const tick = () => {
      gl.uniform1f(uT, frames)
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
      gl.finish()
      frames++

      if (performance.now() - start < 200) {
        requestAnimationFrame(tick)
      } else {
        const elapsed = performance.now() - start
        gl.deleteProgram(prog)
        gl.deleteShader(vs)
        gl.deleteShader(fs)
        gl.deleteBuffer(buf)
        resolve((frames / elapsed) * 1000)
      }
    }

    requestAnimationFrame(tick)
  })
}

export function useGpuTier() {
  return useStore($gpuTier)
}

type GpuTier = 0 | 1 | 2
