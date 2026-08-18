import { type ClassValue, clsx } from 'clsx'
import sanitize from 'sanitize-html'
import { twMerge } from 'tailwind-merge'
import * as THREE from 'three'

import { hexToRgb, rgbToHex } from './color'
import { polyRef } from './poly'
import type { PolyComponent, PolyProps, PolyRef } from './poly'

export { hexToRgb, polyRef, rgbToHex }
export type { PolyComponent, PolyProps, PolyRef }

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))

export const clamp = (v: number, min = 0, max = 1) =>
  Math.min(max, Math.max(min, Number.isFinite(v) ? v : min))

export const smoothstep = (edge0: number, edge1: number, x: number) => {
  const t = clamp((x - edge0) / (edge1 - edge0))

  return t * t * (3 - 2 * t)
}

export const hexToVec3 = (hex: string) => {
  const [r, g, b] = hexToRgb(hex)

  return new THREE.Vector3(r / 255, g / 255, b / 255)
}

export const truncate = (text: string, options: { length: number }) =>
  text.length > options.length ? `${text.slice(0, options.length)}...` : text

export const stripWpStyles = (html: string) =>
  sanitize(html, {
    allowedAttributes: {
      a: ['href', 'target', 'rel', 'name'],
      audio: ['src', 'controls'],
      iframe: ['src', 'width', 'height', 'frameborder', 'allowfullscreen'],
      img: ['src', 'alt', 'width', 'height', 'loading'],
      source: ['src', 'type', 'srcset'],
      td: ['colspan', 'rowspan'],
      th: ['colspan', 'rowspan'],
      video: ['src', 'controls', 'width', 'height', 'poster']
    },
    allowedIframeHostnames: [
      'www.youtube.com',
      'youtube.com',
      'player.vimeo.com'
    ],
    allowedSchemes: ['http', 'https', 'mailto'],
    allowedTags: [
      ...sanitize.defaults.allowedTags,
      'img',
      'figure',
      'figcaption',
      'iframe',
      'video',
      'audio',
      'source',
      'picture'
    ]
  })
