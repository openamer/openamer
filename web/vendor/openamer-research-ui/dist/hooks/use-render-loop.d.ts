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
    el: Element;
    /** Min ms between frames. 0 = no cap (uses requestAnimationFrame).
     *  Anything > 0 uses setTimeout-driven scheduling. */
    minIntervalMs?: number;
    /** Frame callback. Receives the elapsed seconds since the previous
     *  *executed* frame (not since the previous scheduled frame), so
     *  uniforms keyed off this value will not jump after a long pause. */
    onFrame: (deltaSeconds: number) => void;
}
export declare function runRenderLoop({ el, minIntervalMs, onFrame }: RunRenderLoopOptions): () => void;
export {};
