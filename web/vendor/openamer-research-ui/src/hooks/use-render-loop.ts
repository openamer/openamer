'use client'

/**
 * Visibility- and intersection-aware render-loop helper for the WebGL
 * overlays.
 *
 * The overlays were previously running fragment shaders at 60fps for the
 * entire lifetime of the page — including when the tab was hidden, the
 * canvas had been scrolled out of view, or the user had been idle for
 * hours. On retina laptops the compositor cost of mix-blend-mode on a
 * full-viewport canvas plus continuous WebGL rasterisation is enough to
 * keep the GPU hot indefinitely, which is what manifests as "fans go
 * crazy after 2 hours of idle".
 *
 * `runRenderLoop` wraps a frame callback so that it:
 *
 *   1. Pauses entirely when `document.hidden` is true (background tab,
 *      minimised window, screen locked).
 *   2. Pauses when the canvas's bounding rect is offscreen (we tell
 *      `IntersectionObserver` to look at the canvas itself).
 *   3. Optionally caps the frame rate via a min-interval — the previous
 *      `gpuTier === 1 ? setTimeout(loop, 100) : raf` trick is preserved
 *      and extended so even tier-2 GPUs cap at e.g. 30fps for overlays
 *      that don't need 60.
 *
 * The callback receives the *delta* time in seconds since the last call
 * (so `uTime` advances correctly across pauses without ever skipping
 * forward by hours).
 */

interface RunRenderLoopOptions {
  /** Element to observe with IntersectionObserver. When fully out of
   *  view, the loop pauses. Pass the canvas element itself. */
  el: Element
  /** Min ms between frames. 0 = no cap (uses requestAnimationFrame).
   *  Anything > 0 uses setTimeout-driven scheduling. */
  minIntervalMs?: number
  /** Frame callback. Receives the elapsed seconds since the previous
   *  *executed* frame (not since the previous scheduled frame), so
   *  uniforms keyed off this value will not jump after a long pause. */
  onFrame: (deltaSeconds: number) => void
}

export function runRenderLoop({
  el,
  minIntervalMs = 0,
  onFrame
}: RunRenderLoopOptions) {
  let running = true
  let visible = !document.hidden
  let inView = true
  let last = performance.now()
  let raf = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  const onVisibility = () => {
    visible = !document.hidden

    // When we come back from a hidden tab, reset the clock so the next
    // frame's delta is ~one frame, not "hours since I was hidden".
    if (visible) {
      last = performance.now()
      schedule()
    }
  }

  const io = new IntersectionObserver(
    entries => {
      const wasInView = inView
      inView = entries.some(e => e.isIntersecting)

      if (!wasInView && inView) {
        last = performance.now()
        schedule()
      }
    },
    { threshold: 0 }
  )

  io.observe(el)
  document.addEventListener('visibilitychange', onVisibility)

  const tick = () => {
    if (!running) return

    if (!visible || !inView) {
      // Don't reschedule — we'll be re-kicked by visibilitychange or IO.
      return
    }

    const now = performance.now()
    const delta = (now - last) / 1000
    last = now

    onFrame(delta)
    schedule()
  }

  function schedule() {
    if (!running || !visible || !inView) return

    if (minIntervalMs > 0) {
      timer = setTimeout(tick, minIntervalMs)
    } else {
      raf = requestAnimationFrame(tick)
    }
  }

  schedule()

  return () => {
    running = false
    io.disconnect()
    document.removeEventListener('visibilitychange', onVisibility)
    cancelAnimationFrame(raf)

    if (timer !== undefined) {
      clearTimeout(timer)
    }
  }
}
