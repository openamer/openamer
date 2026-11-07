// Upstream-Derived: apps/desktop/src/lib/utils.ts @ 51c68d4ab (MIT)
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
