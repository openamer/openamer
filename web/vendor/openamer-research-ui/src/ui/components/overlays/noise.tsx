'use client'

import { useEffect, useRef } from 'react'
import * as THREE from 'three'

import { $gpuTier, useGpuTier } from '../../../hooks/use-gpu-tier'
import { useSmoothControls } from '../../../hooks/use-smooth-controls'
import { cn, hexToVec3 } from '../../../utils'

import { BLEND_MODES } from './blend-modes'

const vert = /*glsl*/ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const frag = /*glsl*/ `
  uniform vec2 uRes;
  uniform float uDpr, uSize, uDensity, uOpacity;
  uniform vec3 uColor;
  varying vec2 vUv;

  float hash(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
  }

  void main() {
    float n = hash(floor(vUv * uRes / (uSize * uDpr)));
    gl_FragColor = vec4(uColor, step(1.0 - uDensity, n)) * uOpacity;
  }
`

export function Noise({ className, style }: NoiseProps) {
  const gpuTier = useGpuTier()

  const c = useSmoothControls(
    'Effects/Noise',
    {
      blend: { options: BLEND_MODES, value: 'color-dodge' as const },
      color: { value: '#eaeaea' },
      density: { max: 1, min: 0, step: 0.01, value: 0.11 },
      enabled: { value: true },
      opacity: { max: 1, min: 0, step: 0.01, value: 0.55 },
      size: { max: 10, min: 0.1, step: 0.1, value: 1 }
    },
    { collapsed: true }
  )

  const canvasRef = useRef<HTMLCanvasElement>(null)

  const enabled = c.enabled && gpuTier > 0

  // The noise shader is fully deterministic: given the same uniforms it
  // produces an identical output every frame. The previous version ran
  // it at 60fps forever, which on a retina display with mix-blend-mode
  // is enough to peg the GPU/compositor for the entire lifetime of the
  // page (this is the dominant contributor to the "fans go crazy after
  // a few hours of idle" symptom).
  //
  // Instead we render exactly once on mount, and re-render only when
  // the user-controllable uniforms change or the viewport resizes.
  useEffect(() => {
    if (!canvasRef.current || !enabled) {
      return
    }

    let renderer: THREE.WebGLRenderer

    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        canvas: canvasRef.current,
        premultipliedAlpha: false
      })
    } catch {
      $gpuTier.set(0)

      return
    }

    renderer.setClearColor(0x000000, 0)

    const scene = new THREE.Scene()
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
    const geo = new THREE.PlaneGeometry(2, 2)

    const mat = new THREE.ShaderMaterial({
      fragmentShader: frag,
      transparent: true,
      uniforms: {
        uColor: { value: hexToVec3(c.color) },
        uDensity: { value: c.density },
        uDpr: { value: 1 },
        uOpacity: { value: c.opacity },
        uRes: { value: new THREE.Vector2() },
        uSize: { value: c.size }
      },
      vertexShader: vert
    })

    scene.add(new THREE.Mesh(geo, mat))

    // Cap pixel ratio at 1.5 — noise is intentionally pixelated, so the
    // extra retina samples are wasted fillrate.
    const dpr = Math.min(devicePixelRatio, 1.5)

    const render = () => {
      mat.uniforms.uColor.value = hexToVec3(c.color)
      mat.uniforms.uDensity.value = c.density
      mat.uniforms.uOpacity.value = c.opacity
      mat.uniforms.uSize.value = c.size
      mat.uniforms.uDpr.value = dpr
      renderer.render(scene, camera)
    }

    const resize = () => {
      renderer.setSize(innerWidth, innerHeight)
      renderer.setPixelRatio(dpr)
      mat.uniforms.uRes.value.set(innerWidth * dpr, innerHeight * dpr)
      render()
    }

    resize()
    window.addEventListener('resize', resize)

    // Re-render when the tab becomes visible again, in case the GL
    // context was discarded by the browser while the page was
    // backgrounded — otherwise we can come back to a transparent canvas.
    const onVisibility = () => {
      if (!document.hidden) render()
    }

    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', onVisibility)

      mat.dispose()
      geo.dispose()
      renderer.dispose()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    enabled,
    gpuTier,
    c.color,
    c.density,
    c.opacity,
    c.size
  ])

  if (!enabled) {
    return null
  }

  return (
    <canvas
      className={cn('h-full w-full', className)}
      ref={canvasRef}
      style={{ mixBlendMode: c.blend, ...style }}
    />
  )
}

interface NoiseProps {
  className?: string
  style?: React.CSSProperties
}
