// Upstream-Derived: apps/desktop/src/lib/mutable-ref.ts @ e003c53b0 (MIT)
import type { MutableRefObject } from 'react'

/** Imperative ref write — extracted so react-compiler doesn't flag hook-arg refs. */
export function setMutableRef<T>(ref: MutableRefObject<T>, value: T) {
  ref.current = value
}
