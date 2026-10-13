"use client";
import { jsx } from "react/jsx-runtime";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { $gpuTier, useGpuTier } from "../../../hooks/use-gpu-tier.js";
import { runRenderLoop } from "../../../hooks/use-render-loop.js";
import { useSmoothControls } from "../../../hooks/use-smooth-controls.js";
import { cn } from "../../../utils/index.js";
import { BLEND_MODES } from "./blend-modes.js";
const vert = (
  /*glsl*/
  `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`
);
const frag = (
  /*glsl*/
  `
  uniform float uTime, uAlpha, uIntensity, uChroma, uSpeed, uSparsity;
  uniform vec3 uColor;
  varying vec2 vUv;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

  vec2 hash2(vec2 p) {
    vec3 q = fract(vec3(p.xyx) * vec3(.1031, .1030, .0973));
    q += dot(q, q.yzx + 33.33);
    return fract((q.xx + q.yz) * q.zy);
  }

  float dither(vec2 p, float a) {
    return step(mod(floor(p.x) + floor(p.y) * 2.0, 4.0) / 4.0, a);
  }

  void main() {
    vec3 col = vec3(0.0);
    float t = uTime * uSpeed;
    float tSlow = floor(t / 3.0);
    float dit = dither(gl_FragCoord.xy * 0.5, 0.7);

    for (float i = 0.0; i < 6.0; i++) {
      float seed = i * 137.3;
      float epoch = floor((t + hash(vec2(seed, 77.7)) * 200.0) / (4.0 + hash(vec2(seed, 0.0)) * 6.0));
      float life = fract((t + hash(vec2(seed, 77.7)) * 200.0) / (4.0 + hash(vec2(seed, 0.0)) * 6.0));

      if (hash(vec2(epoch, seed)) > 1.0 - uSparsity * 0.7) continue;

      vec2 center = vec2(hash(vec2(epoch, seed + 13.1)), hash(vec2(epoch, seed + 27.3)));
      vec2 size = vec2(0.015 + hash(vec2(epoch, seed + 41.5)) * 0.08, 0.008 + hash(vec2(epoch, seed + 53.7)) * 0.04);
      vec2 d = abs(vUv - center);

      if (d.x < size.x && d.y < size.y) {
        float fade = smoothstep(0.0, 0.05, life) * smoothstep(1.0, 0.95, life);
        vec2 gUV = vUv + (hash2(vec2(epoch, seed + 200.0)) - 0.5) * 0.08 * uIntensity;
        float shift = uChroma * 0.015 * (sin(t * 2.0 + hash(vec2(epoch, seed)) * 6.28) * 0.3 + 0.7);

        col += uColor * vec3(
          hash(gUV * 50.0 + vec2(shift, 0.0) + epoch),
          hash(gUV * 50.0 + epoch),
          hash(gUV * 50.0 - vec2(shift, 0.0) + epoch)
        ) * dither(gl_FragCoord.xy * 0.5, fade * 0.8 + 0.2) * uIntensity * 0.7;
      }
    }

    for (float i = 0.0; i < 12.0; i++) {
      float seed = i * 211.7 + 1000.0;
      float epoch = floor((t + hash(vec2(seed, 77.7)) * 150.0) / (3.0 + hash(vec2(seed, 0.0)) * 5.0));
      float life = fract((t + hash(vec2(seed, 77.7)) * 150.0) / (3.0 + hash(vec2(seed, 0.0)) * 5.0));

      if (hash(vec2(epoch, seed)) > 1.0 - uSparsity * 0.5) continue;

      vec2 pos = vec2(hash(vec2(epoch, seed + 13.1)), hash(vec2(epoch, seed + 27.3)));
      float px = 0.003 + hash(vec2(epoch, seed + 41.5)) * 0.008;

      if (abs(vUv.x - pos.x) < px && abs(vUv.y - pos.y) < px) {
        float fade = smoothstep(0.0, 0.1, life) * smoothstep(1.0, 0.9, life);
        vec3 c = uColor;
        float cs = hash(vec2(epoch, seed + 700.0));

        if (cs < 0.2) c.r *= 1.8 * uChroma;
        else if (cs < 0.4) c.b *= 1.8 * uChroma;

        col += c * dither(gl_FragCoord.xy * 0.5, fade * 0.9) * uIntensity;
      }
    }

    float tearSize = 25.0 + uSparsity * 10.0;
    float tearThresh = 0.85 + uSparsity * 0.1;

    float hY = floor(vUv.y * tearSize);
    if (step(tearThresh, hash(vec2(hY, tSlow))) > 0.0) {
      float shift = (hash(vec2(hY, tSlow + 50.0)) - 0.5) * 0.25 * uIntensity;
      col += uColor * step(0.4, hash(vec2(vUv.x + shift, hY + tSlow))) * dit * uIntensity * 0.5;
    }

    float vX = floor(vUv.x * tearSize);
    if (step(tearThresh, hash(vec2(vX, tSlow + 100.0))) > 0.0) {
      float shift = (hash(vec2(vX, tSlow + 150.0)) - 0.5) * 0.25 * uIntensity;
      col += uColor * step(0.4, hash(vec2(vX + tSlow, vUv.y + shift))) * dit * uIntensity * 0.5;
    }

    gl_FragColor = vec4(col * uAlpha, max(col.r, max(col.g, col.b)) * uAlpha);
  }
`
);
export function Glitch({ className, style }) {
  const gpuTier = useGpuTier();
  const c = useSmoothControls(
    "Effects/Glitch",
    {
      alpha: { max: 2, min: 0, step: 0.01, value: 0.25 },
      blend: { options: BLEND_MODES, value: "difference" },
      chroma: { max: 3, min: 0, step: 0.01, value: 1.17 },
      color: { value: "#ffe6cb" },
      enabled: { value: true },
      intensity: { max: 1, min: 0, step: 0.01, value: 0.59 },
      sparsity: { max: 1, min: 0, step: 0.01, value: 0.21 },
      speed: { max: 10, min: 0.1, step: 0.1, value: 1 }
    },
    { collapsed: true }
  );
  const ref = useRef(null);
  const cRef = useRef(c);
  cRef.current = c;
  const enabled = c.enabled && gpuTier > 0;
  useEffect(() => {
    if (!ref.current || !enabled) {
      return;
    }
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        canvas: ref.current
      });
    } catch {
      $gpuTier.set(0);
      return;
    }
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const geo = new THREE.PlaneGeometry(2, 2);
    const scene = new THREE.Scene();
    const mat = new THREE.ShaderMaterial({
      fragmentShader: frag,
      transparent: true,
      uniforms: {
        uAlpha: { value: c.alpha },
        uChroma: { value: c.chroma },
        uColor: { value: new THREE.Color(c.color) },
        uIntensity: { value: c.intensity },
        uSparsity: { value: c.sparsity },
        uSpeed: { value: c.speed },
        uTime: { value: 0 }
      },
      vertexShader: vert
    });
    scene.add(new THREE.Mesh(geo, mat));
    const resize = () => {
      renderer.setSize(innerWidth, innerHeight);
      renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    };
    resize();
    window.addEventListener("resize", resize);
    let time = 0;
    const minIntervalMs = gpuTier === 1 ? 100 : 33;
    const dispose = runRenderLoop({
      el: ref.current,
      minIntervalMs,
      onFrame: (deltaSeconds) => {
        time += deltaSeconds;
        const v = cRef.current;
        mat.uniforms.uTime.value = time;
        mat.uniforms.uAlpha.value = v.alpha;
        mat.uniforms.uChroma.value = v.chroma;
        mat.uniforms.uIntensity.value = v.intensity;
        mat.uniforms.uSparsity.value = v.sparsity;
        mat.uniforms.uSpeed.value = v.speed;
        mat.uniforms.uColor.value.set(v.color);
        renderer.render(scene, camera);
      }
    });
    return () => {
      window.removeEventListener("resize", resize);
      dispose();
      mat.dispose();
      geo.dispose();
      renderer.dispose();
    };
  }, [enabled, gpuTier]);
  if (!enabled) {
    return null;
  }
  return /* @__PURE__ */ jsx(
    "canvas",
    {
      className: cn("h-full w-full", className),
      ref,
      style: {
        mixBlendMode: c.blend,
        ...style
      }
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZUVmZmVjdCwgdXNlUmVmIH0gZnJvbSAncmVhY3QnXG5pbXBvcnQgKiBhcyBUSFJFRSBmcm9tICd0aHJlZSdcblxuaW1wb3J0IHsgJGdwdVRpZXIsIHVzZUdwdVRpZXIgfSBmcm9tICcuLi8uLi8uLi9ob29rcy91c2UtZ3B1LXRpZXInXG5pbXBvcnQgeyBydW5SZW5kZXJMb29wIH0gZnJvbSAnLi4vLi4vLi4vaG9va3MvdXNlLXJlbmRlci1sb29wJ1xuaW1wb3J0IHsgdXNlU21vb3RoQ29udHJvbHMgfSBmcm9tICcuLi8uLi8uLi9ob29rcy91c2Utc21vb3RoLWNvbnRyb2xzJ1xuaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi8uLi91dGlscydcblxuaW1wb3J0IHsgQkxFTkRfTU9ERVMgfSBmcm9tICcuL2JsZW5kLW1vZGVzJ1xuXG5jb25zdCB2ZXJ0ID0gLypnbHNsKi8gYFxuICB2YXJ5aW5nIHZlYzIgdlV2O1xuICB2b2lkIG1haW4oKSB7XG4gICAgdlV2ID0gdXY7XG4gICAgZ2xfUG9zaXRpb24gPSBwcm9qZWN0aW9uTWF0cml4ICogbW9kZWxWaWV3TWF0cml4ICogdmVjNChwb3NpdGlvbiwgMS4wKTtcbiAgfVxuYFxuXG5jb25zdCBmcmFnID0gLypnbHNsKi8gYFxuICB1bmlmb3JtIGZsb2F0IHVUaW1lLCB1QWxwaGEsIHVJbnRlbnNpdHksIHVDaHJvbWEsIHVTcGVlZCwgdVNwYXJzaXR5O1xuICB1bmlmb3JtIHZlYzMgdUNvbG9yO1xuICB2YXJ5aW5nIHZlYzIgdlV2O1xuXG4gIGZsb2F0IGhhc2godmVjMiBwKSB7IHJldHVybiBmcmFjdChzaW4oZG90KHAsIHZlYzIoMTI3LjEsIDMxMS43KSkpICogNDM3NTguNTQ1Myk7IH1cblxuICB2ZWMyIGhhc2gyKHZlYzIgcCkge1xuICAgIHZlYzMgcSA9IGZyYWN0KHZlYzMocC54eXgpICogdmVjMyguMTAzMSwgLjEwMzAsIC4wOTczKSk7XG4gICAgcSArPSBkb3QocSwgcS55enggKyAzMy4zMyk7XG4gICAgcmV0dXJuIGZyYWN0KChxLnh4ICsgcS55eikgKiBxLnp5KTtcbiAgfVxuXG4gIGZsb2F0IGRpdGhlcih2ZWMyIHAsIGZsb2F0IGEpIHtcbiAgICByZXR1cm4gc3RlcChtb2QoZmxvb3IocC54KSArIGZsb29yKHAueSkgKiAyLjAsIDQuMCkgLyA0LjAsIGEpO1xuICB9XG5cbiAgdm9pZCBtYWluKCkge1xuICAgIHZlYzMgY29sID0gdmVjMygwLjApO1xuICAgIGZsb2F0IHQgPSB1VGltZSAqIHVTcGVlZDtcbiAgICBmbG9hdCB0U2xvdyA9IGZsb29yKHQgLyAzLjApO1xuICAgIGZsb2F0IGRpdCA9IGRpdGhlcihnbF9GcmFnQ29vcmQueHkgKiAwLjUsIDAuNyk7XG5cbiAgICBmb3IgKGZsb2F0IGkgPSAwLjA7IGkgPCA2LjA7IGkrKykge1xuICAgICAgZmxvYXQgc2VlZCA9IGkgKiAxMzcuMztcbiAgICAgIGZsb2F0IGVwb2NoID0gZmxvb3IoKHQgKyBoYXNoKHZlYzIoc2VlZCwgNzcuNykpICogMjAwLjApIC8gKDQuMCArIGhhc2godmVjMihzZWVkLCAwLjApKSAqIDYuMCkpO1xuICAgICAgZmxvYXQgbGlmZSA9IGZyYWN0KCh0ICsgaGFzaCh2ZWMyKHNlZWQsIDc3LjcpKSAqIDIwMC4wKSAvICg0LjAgKyBoYXNoKHZlYzIoc2VlZCwgMC4wKSkgKiA2LjApKTtcblxuICAgICAgaWYgKGhhc2godmVjMihlcG9jaCwgc2VlZCkpID4gMS4wIC0gdVNwYXJzaXR5ICogMC43KSBjb250aW51ZTtcblxuICAgICAgdmVjMiBjZW50ZXIgPSB2ZWMyKGhhc2godmVjMihlcG9jaCwgc2VlZCArIDEzLjEpKSwgaGFzaCh2ZWMyKGVwb2NoLCBzZWVkICsgMjcuMykpKTtcbiAgICAgIHZlYzIgc2l6ZSA9IHZlYzIoMC4wMTUgKyBoYXNoKHZlYzIoZXBvY2gsIHNlZWQgKyA0MS41KSkgKiAwLjA4LCAwLjAwOCArIGhhc2godmVjMihlcG9jaCwgc2VlZCArIDUzLjcpKSAqIDAuMDQpO1xuICAgICAgdmVjMiBkID0gYWJzKHZVdiAtIGNlbnRlcik7XG5cbiAgICAgIGlmIChkLnggPCBzaXplLnggJiYgZC55IDwgc2l6ZS55KSB7XG4gICAgICAgIGZsb2F0IGZhZGUgPSBzbW9vdGhzdGVwKDAuMCwgMC4wNSwgbGlmZSkgKiBzbW9vdGhzdGVwKDEuMCwgMC45NSwgbGlmZSk7XG4gICAgICAgIHZlYzIgZ1VWID0gdlV2ICsgKGhhc2gyKHZlYzIoZXBvY2gsIHNlZWQgKyAyMDAuMCkpIC0gMC41KSAqIDAuMDggKiB1SW50ZW5zaXR5O1xuICAgICAgICBmbG9hdCBzaGlmdCA9IHVDaHJvbWEgKiAwLjAxNSAqIChzaW4odCAqIDIuMCArIGhhc2godmVjMihlcG9jaCwgc2VlZCkpICogNi4yOCkgKiAwLjMgKyAwLjcpO1xuXG4gICAgICAgIGNvbCArPSB1Q29sb3IgKiB2ZWMzKFxuICAgICAgICAgIGhhc2goZ1VWICogNTAuMCArIHZlYzIoc2hpZnQsIDAuMCkgKyBlcG9jaCksXG4gICAgICAgICAgaGFzaChnVVYgKiA1MC4wICsgZXBvY2gpLFxuICAgICAgICAgIGhhc2goZ1VWICogNTAuMCAtIHZlYzIoc2hpZnQsIDAuMCkgKyBlcG9jaClcbiAgICAgICAgKSAqIGRpdGhlcihnbF9GcmFnQ29vcmQueHkgKiAwLjUsIGZhZGUgKiAwLjggKyAwLjIpICogdUludGVuc2l0eSAqIDAuNztcbiAgICAgIH1cbiAgICB9XG5cbiAgICBmb3IgKGZsb2F0IGkgPSAwLjA7IGkgPCAxMi4wOyBpKyspIHtcbiAgICAgIGZsb2F0IHNlZWQgPSBpICogMjExLjcgKyAxMDAwLjA7XG4gICAgICBmbG9hdCBlcG9jaCA9IGZsb29yKCh0ICsgaGFzaCh2ZWMyKHNlZWQsIDc3LjcpKSAqIDE1MC4wKSAvICgzLjAgKyBoYXNoKHZlYzIoc2VlZCwgMC4wKSkgKiA1LjApKTtcbiAgICAgIGZsb2F0IGxpZmUgPSBmcmFjdCgodCArIGhhc2godmVjMihzZWVkLCA3Ny43KSkgKiAxNTAuMCkgLyAoMy4wICsgaGFzaCh2ZWMyKHNlZWQsIDAuMCkpICogNS4wKSk7XG5cbiAgICAgIGlmIChoYXNoKHZlYzIoZXBvY2gsIHNlZWQpKSA+IDEuMCAtIHVTcGFyc2l0eSAqIDAuNSkgY29udGludWU7XG5cbiAgICAgIHZlYzIgcG9zID0gdmVjMihoYXNoKHZlYzIoZXBvY2gsIHNlZWQgKyAxMy4xKSksIGhhc2godmVjMihlcG9jaCwgc2VlZCArIDI3LjMpKSk7XG4gICAgICBmbG9hdCBweCA9IDAuMDAzICsgaGFzaCh2ZWMyKGVwb2NoLCBzZWVkICsgNDEuNSkpICogMC4wMDg7XG5cbiAgICAgIGlmIChhYnModlV2LnggLSBwb3MueCkgPCBweCAmJiBhYnModlV2LnkgLSBwb3MueSkgPCBweCkge1xuICAgICAgICBmbG9hdCBmYWRlID0gc21vb3Roc3RlcCgwLjAsIDAuMSwgbGlmZSkgKiBzbW9vdGhzdGVwKDEuMCwgMC45LCBsaWZlKTtcbiAgICAgICAgdmVjMyBjID0gdUNvbG9yO1xuICAgICAgICBmbG9hdCBjcyA9IGhhc2godmVjMihlcG9jaCwgc2VlZCArIDcwMC4wKSk7XG5cbiAgICAgICAgaWYgKGNzIDwgMC4yKSBjLnIgKj0gMS44ICogdUNocm9tYTtcbiAgICAgICAgZWxzZSBpZiAoY3MgPCAwLjQpIGMuYiAqPSAxLjggKiB1Q2hyb21hO1xuXG4gICAgICAgIGNvbCArPSBjICogZGl0aGVyKGdsX0ZyYWdDb29yZC54eSAqIDAuNSwgZmFkZSAqIDAuOSkgKiB1SW50ZW5zaXR5O1xuICAgICAgfVxuICAgIH1cblxuICAgIGZsb2F0IHRlYXJTaXplID0gMjUuMCArIHVTcGFyc2l0eSAqIDEwLjA7XG4gICAgZmxvYXQgdGVhclRocmVzaCA9IDAuODUgKyB1U3BhcnNpdHkgKiAwLjE7XG5cbiAgICBmbG9hdCBoWSA9IGZsb29yKHZVdi55ICogdGVhclNpemUpO1xuICAgIGlmIChzdGVwKHRlYXJUaHJlc2gsIGhhc2godmVjMihoWSwgdFNsb3cpKSkgPiAwLjApIHtcbiAgICAgIGZsb2F0IHNoaWZ0ID0gKGhhc2godmVjMihoWSwgdFNsb3cgKyA1MC4wKSkgLSAwLjUpICogMC4yNSAqIHVJbnRlbnNpdHk7XG4gICAgICBjb2wgKz0gdUNvbG9yICogc3RlcCgwLjQsIGhhc2godmVjMih2VXYueCArIHNoaWZ0LCBoWSArIHRTbG93KSkpICogZGl0ICogdUludGVuc2l0eSAqIDAuNTtcbiAgICB9XG5cbiAgICBmbG9hdCB2WCA9IGZsb29yKHZVdi54ICogdGVhclNpemUpO1xuICAgIGlmIChzdGVwKHRlYXJUaHJlc2gsIGhhc2godmVjMih2WCwgdFNsb3cgKyAxMDAuMCkpKSA+IDAuMCkge1xuICAgICAgZmxvYXQgc2hpZnQgPSAoaGFzaCh2ZWMyKHZYLCB0U2xvdyArIDE1MC4wKSkgLSAwLjUpICogMC4yNSAqIHVJbnRlbnNpdHk7XG4gICAgICBjb2wgKz0gdUNvbG9yICogc3RlcCgwLjQsIGhhc2godmVjMih2WCArIHRTbG93LCB2VXYueSArIHNoaWZ0KSkpICogZGl0ICogdUludGVuc2l0eSAqIDAuNTtcbiAgICB9XG5cbiAgICBnbF9GcmFnQ29sb3IgPSB2ZWM0KGNvbCAqIHVBbHBoYSwgbWF4KGNvbC5yLCBtYXgoY29sLmcsIGNvbC5iKSkgKiB1QWxwaGEpO1xuICB9XG5gXG5cbmV4cG9ydCBmdW5jdGlvbiBHbGl0Y2goeyBjbGFzc05hbWUsIHN0eWxlIH06IEdsaXRjaFByb3BzKSB7XG4gIGNvbnN0IGdwdVRpZXIgPSB1c2VHcHVUaWVyKClcblxuICBjb25zdCBjID0gdXNlU21vb3RoQ29udHJvbHMoXG4gICAgJ0VmZmVjdHMvR2xpdGNoJyxcbiAgICB7XG4gICAgICBhbHBoYTogeyBtYXg6IDIsIG1pbjogMCwgc3RlcDogMC4wMSwgdmFsdWU6IDAuMjUgfSxcbiAgICAgIGJsZW5kOiB7IG9wdGlvbnM6IEJMRU5EX01PREVTLCB2YWx1ZTogJ2RpZmZlcmVuY2UnIH0sXG4gICAgICBjaHJvbWE6IHsgbWF4OiAzLCBtaW46IDAsIHN0ZXA6IDAuMDEsIHZhbHVlOiAxLjE3IH0sXG4gICAgICBjb2xvcjogeyB2YWx1ZTogJyNmZmU2Y2InIH0sXG4gICAgICBlbmFibGVkOiB7IHZhbHVlOiB0cnVlIH0sXG4gICAgICBpbnRlbnNpdHk6IHsgbWF4OiAxLCBtaW46IDAsIHN0ZXA6IDAuMDEsIHZhbHVlOiAwLjU5IH0sXG4gICAgICBzcGFyc2l0eTogeyBtYXg6IDEsIG1pbjogMCwgc3RlcDogMC4wMSwgdmFsdWU6IDAuMjEgfSxcbiAgICAgIHNwZWVkOiB7IG1heDogMTAsIG1pbjogMC4xLCBzdGVwOiAwLjEsIHZhbHVlOiAxIH1cbiAgICB9LFxuICAgIHsgY29sbGFwc2VkOiB0cnVlIH1cbiAgKVxuXG4gIGNvbnN0IHJlZiA9IHVzZVJlZjxIVE1MQ2FudmFzRWxlbWVudD4obnVsbClcbiAgY29uc3QgY1JlZiA9IHVzZVJlZihjKVxuICBjUmVmLmN1cnJlbnQgPSBjXG5cbiAgY29uc3QgZW5hYmxlZCA9IGMuZW5hYmxlZCAmJiBncHVUaWVyID4gMFxuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgaWYgKCFyZWYuY3VycmVudCB8fCAhZW5hYmxlZCkge1xuICAgICAgcmV0dXJuXG4gICAgfVxuXG4gICAgbGV0IHJlbmRlcmVyOiBUSFJFRS5XZWJHTFJlbmRlcmVyXG5cbiAgICB0cnkge1xuICAgICAgcmVuZGVyZXIgPSBuZXcgVEhSRUUuV2ViR0xSZW5kZXJlcih7XG4gICAgICAgIGFscGhhOiB0cnVlLFxuICAgICAgICBjYW52YXM6IHJlZi5jdXJyZW50XG4gICAgICB9KVxuICAgIH0gY2F0Y2gge1xuICAgICAgLy8gU2VlIG5vdGUgaW4gbm9pc2UudHN4IFx1MjAxNCBlYWdlciBncHUtdGllciBkZXRlY3Rpb24gc2hvdWxkIGtlZXAgdXNcbiAgICAgIC8vIG91dCBvZiBoZXJlLCBidXQgaWYgdGhlIGRyaXZlciBmYWlscyB0aGUgcmVuZGVyZXIgY29uc3RydWN0b3JcbiAgICAgIC8vIGFueXdheSwgZG93bmdyYWRlIHNvIG90aGVyIG92ZXJsYXlzIHN0b3AgdHJ5aW5nIHRvby5cbiAgICAgICRncHVUaWVyLnNldCgwKVxuXG4gICAgICByZXR1cm5cbiAgICB9XG5cbiAgICBjb25zdCBjYW1lcmEgPSBuZXcgVEhSRUUuT3J0aG9ncmFwaGljQ2FtZXJhKC0xLCAxLCAxLCAtMSwgMCwgMSlcbiAgICBjb25zdCBnZW8gPSBuZXcgVEhSRUUuUGxhbmVHZW9tZXRyeSgyLCAyKVxuICAgIGNvbnN0IHNjZW5lID0gbmV3IFRIUkVFLlNjZW5lKClcblxuICAgIGNvbnN0IG1hdCA9IG5ldyBUSFJFRS5TaGFkZXJNYXRlcmlhbCh7XG4gICAgICBmcmFnbWVudFNoYWRlcjogZnJhZyxcbiAgICAgIHRyYW5zcGFyZW50OiB0cnVlLFxuICAgICAgdW5pZm9ybXM6IHtcbiAgICAgICAgdUFscGhhOiB7IHZhbHVlOiBjLmFscGhhIH0sXG4gICAgICAgIHVDaHJvbWE6IHsgdmFsdWU6IGMuY2hyb21hIH0sXG4gICAgICAgIHVDb2xvcjogeyB2YWx1ZTogbmV3IFRIUkVFLkNvbG9yKGMuY29sb3IpIH0sXG4gICAgICAgIHVJbnRlbnNpdHk6IHsgdmFsdWU6IGMuaW50ZW5zaXR5IH0sXG4gICAgICAgIHVTcGFyc2l0eTogeyB2YWx1ZTogYy5zcGFyc2l0eSB9LFxuICAgICAgICB1U3BlZWQ6IHsgdmFsdWU6IGMuc3BlZWQgfSxcbiAgICAgICAgdVRpbWU6IHsgdmFsdWU6IDAgfVxuICAgICAgfSxcbiAgICAgIHZlcnRleFNoYWRlcjogdmVydFxuICAgIH0pXG5cbiAgICBzY2VuZS5hZGQobmV3IFRIUkVFLk1lc2goZ2VvLCBtYXQpKVxuXG4gICAgY29uc3QgcmVzaXplID0gKCkgPT4ge1xuICAgICAgcmVuZGVyZXIuc2V0U2l6ZShpbm5lcldpZHRoLCBpbm5lckhlaWdodClcbiAgICAgIC8vIENhcCBEUFIgYXQgMS41IFx1MjAxNCBhdCBmdWxsIHJldGluYSAoMngpIHRoZSBnbGl0Y2ggc2hhZGVyIGlzIG9uZVxuICAgICAgLy8gb2YgdGhlIGhlYXZpZXN0IGZpbGxyYXRlIGNvbnN1bWVycyBpbiB0aGUgYXBwLCBhbmQgdGhlIHZpc3VhbFxuICAgICAgLy8gZGlmZmVyZW5jZSBpcyB0aW55IGJlY2F1c2UgaXQncyBhIGNocm9tYXRpYy1ub2lzZSBlZmZlY3QuXG4gICAgICByZW5kZXJlci5zZXRQaXhlbFJhdGlvKE1hdGgubWluKGRldmljZVBpeGVsUmF0aW8sIDEuNSkpXG4gICAgfVxuXG4gICAgcmVzaXplKClcbiAgICB3aW5kb3cuYWRkRXZlbnRMaXN0ZW5lcigncmVzaXplJywgcmVzaXplKVxuXG4gICAgbGV0IHRpbWUgPSAwXG5cbiAgICAvLyBncHUtdGllciAxIFx1MjE5MiB+MTBmcHMgKGxlZ2FjeSksIGdwdS10aWVyIDIgXHUyMTkyIH4zMGZwcyAod2FzIDYwZnBzKS5cbiAgICAvLyBHbGl0Y2ggaXMgYSBiYWNrZ3JvdW5kIGFtYmllbnQgZWZmZWN0OyB1c2VycyB3b24ndCBub3RpY2UgMzAgdnNcbiAgICAvLyA2MCBidXQgdGhlIEdQVSBhYnNvbHV0ZWx5IHdpbGwuXG4gICAgY29uc3QgbWluSW50ZXJ2YWxNcyA9IGdwdVRpZXIgPT09IDEgPyAxMDAgOiAzM1xuXG4gICAgY29uc3QgZGlzcG9zZSA9IHJ1blJlbmRlckxvb3Aoe1xuICAgICAgZWw6IHJlZi5jdXJyZW50LFxuICAgICAgbWluSW50ZXJ2YWxNcyxcbiAgICAgIG9uRnJhbWU6IGRlbHRhU2Vjb25kcyA9PiB7XG4gICAgICAgIHRpbWUgKz0gZGVsdGFTZWNvbmRzXG5cbiAgICAgICAgY29uc3QgdiA9IGNSZWYuY3VycmVudFxuXG4gICAgICAgIG1hdC51bmlmb3Jtcy51VGltZS52YWx1ZSA9IHRpbWVcbiAgICAgICAgbWF0LnVuaWZvcm1zLnVBbHBoYS52YWx1ZSA9IHYuYWxwaGFcbiAgICAgICAgbWF0LnVuaWZvcm1zLnVDaHJvbWEudmFsdWUgPSB2LmNocm9tYVxuICAgICAgICBtYXQudW5pZm9ybXMudUludGVuc2l0eS52YWx1ZSA9IHYuaW50ZW5zaXR5XG4gICAgICAgIG1hdC51bmlmb3Jtcy51U3BhcnNpdHkudmFsdWUgPSB2LnNwYXJzaXR5XG4gICAgICAgIG1hdC51bmlmb3Jtcy51U3BlZWQudmFsdWUgPSB2LnNwZWVkXG4gICAgICAgIG1hdC51bmlmb3Jtcy51Q29sb3IudmFsdWUuc2V0KHYuY29sb3IpXG5cbiAgICAgICAgcmVuZGVyZXIucmVuZGVyKHNjZW5lLCBjYW1lcmEpXG4gICAgICB9XG4gICAgfSlcblxuICAgIHJldHVybiAoKSA9PiB7XG4gICAgICB3aW5kb3cucmVtb3ZlRXZlbnRMaXN0ZW5lcigncmVzaXplJywgcmVzaXplKVxuICAgICAgZGlzcG9zZSgpXG5cbiAgICAgIG1hdC5kaXNwb3NlKClcbiAgICAgIGdlby5kaXNwb3NlKClcbiAgICAgIHJlbmRlcmVyLmRpc3Bvc2UoKVxuICAgIH1cbiAgICAvLyBlc2xpbnQtZGlzYWJsZS1uZXh0LWxpbmUgcmVhY3QtaG9va3MvZXhoYXVzdGl2ZS1kZXBzXG4gIH0sIFtlbmFibGVkLCBncHVUaWVyXSlcblxuICBpZiAoIWVuYWJsZWQpIHtcbiAgICByZXR1cm4gbnVsbFxuICB9XG5cbiAgcmV0dXJuIChcbiAgICA8Y2FudmFzXG4gICAgICBjbGFzc05hbWU9e2NuKCdoLWZ1bGwgdy1mdWxsJywgY2xhc3NOYW1lKX1cbiAgICAgIHJlZj17cmVmfVxuICAgICAgc3R5bGU9e3tcbiAgICAgICAgbWl4QmxlbmRNb2RlOiBjLmJsZW5kIGFzIFJlYWN0LkNTU1Byb3BlcnRpZXNbJ21peEJsZW5kTW9kZSddLFxuICAgICAgICAuLi5zdHlsZVxuICAgICAgfX1cbiAgICAvPlxuICApXG59XG5cbmludGVyZmFjZSBHbGl0Y2hQcm9wcyB7XG4gIGNsYXNzTmFtZT86IHN0cmluZ1xuICBzdHlsZT86IFJlYWN0LkNTU1Byb3BlcnRpZXNcbn0iXSwKICAibWFwcGluZ3MiOiAiO0FBb09JO0FBbE9KLFNBQVMsV0FBVyxjQUFjO0FBQ2xDLFlBQVksV0FBVztBQUV2QixTQUFTLFVBQVUsa0JBQWtCO0FBQ3JDLFNBQVMscUJBQXFCO0FBQzlCLFNBQVMseUJBQXlCO0FBQ2xDLFNBQVMsVUFBVTtBQUVuQixTQUFTLG1CQUFtQjtBQUU1QixNQUFNO0FBQUE7QUFBQSxFQUFnQjtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBUXRCLE1BQU07QUFBQTtBQUFBLEVBQWdCO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBd0ZmLGdCQUFTLE9BQU8sRUFBRSxXQUFXLE1BQU0sR0FBZ0I7QUFDeEQsUUFBTSxVQUFVLFdBQVc7QUFFM0IsUUFBTSxJQUFJO0FBQUEsSUFDUjtBQUFBLElBQ0E7QUFBQSxNQUNFLE9BQU8sRUFBRSxLQUFLLEdBQUcsS0FBSyxHQUFHLE1BQU0sTUFBTSxPQUFPLEtBQUs7QUFBQSxNQUNqRCxPQUFPLEVBQUUsU0FBUyxhQUFhLE9BQU8sYUFBYTtBQUFBLE1BQ25ELFFBQVEsRUFBRSxLQUFLLEdBQUcsS0FBSyxHQUFHLE1BQU0sTUFBTSxPQUFPLEtBQUs7QUFBQSxNQUNsRCxPQUFPLEVBQUUsT0FBTyxVQUFVO0FBQUEsTUFDMUIsU0FBUyxFQUFFLE9BQU8sS0FBSztBQUFBLE1BQ3ZCLFdBQVcsRUFBRSxLQUFLLEdBQUcsS0FBSyxHQUFHLE1BQU0sTUFBTSxPQUFPLEtBQUs7QUFBQSxNQUNyRCxVQUFVLEVBQUUsS0FBSyxHQUFHLEtBQUssR0FBRyxNQUFNLE1BQU0sT0FBTyxLQUFLO0FBQUEsTUFDcEQsT0FBTyxFQUFFLEtBQUssSUFBSSxLQUFLLEtBQUssTUFBTSxLQUFLLE9BQU8sRUFBRTtBQUFBLElBQ2xEO0FBQUEsSUFDQSxFQUFFLFdBQVcsS0FBSztBQUFBLEVBQ3BCO0FBRUEsUUFBTSxNQUFNLE9BQTBCLElBQUk7QUFDMUMsUUFBTSxPQUFPLE9BQU8sQ0FBQztBQUNyQixPQUFLLFVBQVU7QUFFZixRQUFNLFVBQVUsRUFBRSxXQUFXLFVBQVU7QUFFdkMsWUFBVSxNQUFNO0FBQ2QsUUFBSSxDQUFDLElBQUksV0FBVyxDQUFDLFNBQVM7QUFDNUI7QUFBQSxJQUNGO0FBRUEsUUFBSTtBQUVKLFFBQUk7QUFDRixpQkFBVyxJQUFJLE1BQU0sY0FBYztBQUFBLFFBQ2pDLE9BQU87QUFBQSxRQUNQLFFBQVEsSUFBSTtBQUFBLE1BQ2QsQ0FBQztBQUFBLElBQ0gsUUFBUTtBQUlOLGVBQVMsSUFBSSxDQUFDO0FBRWQ7QUFBQSxJQUNGO0FBRUEsVUFBTSxTQUFTLElBQUksTUFBTSxtQkFBbUIsSUFBSSxHQUFHLEdBQUcsSUFBSSxHQUFHLENBQUM7QUFDOUQsVUFBTSxNQUFNLElBQUksTUFBTSxjQUFjLEdBQUcsQ0FBQztBQUN4QyxVQUFNLFFBQVEsSUFBSSxNQUFNLE1BQU07QUFFOUIsVUFBTSxNQUFNLElBQUksTUFBTSxlQUFlO0FBQUEsTUFDbkMsZ0JBQWdCO0FBQUEsTUFDaEIsYUFBYTtBQUFBLE1BQ2IsVUFBVTtBQUFBLFFBQ1IsUUFBUSxFQUFFLE9BQU8sRUFBRSxNQUFNO0FBQUEsUUFDekIsU0FBUyxFQUFFLE9BQU8sRUFBRSxPQUFPO0FBQUEsUUFDM0IsUUFBUSxFQUFFLE9BQU8sSUFBSSxNQUFNLE1BQU0sRUFBRSxLQUFLLEVBQUU7QUFBQSxRQUMxQyxZQUFZLEVBQUUsT0FBTyxFQUFFLFVBQVU7QUFBQSxRQUNqQyxXQUFXLEVBQUUsT0FBTyxFQUFFLFNBQVM7QUFBQSxRQUMvQixRQUFRLEVBQUUsT0FBTyxFQUFFLE1BQU07QUFBQSxRQUN6QixPQUFPLEVBQUUsT0FBTyxFQUFFO0FBQUEsTUFDcEI7QUFBQSxNQUNBLGNBQWM7QUFBQSxJQUNoQixDQUFDO0FBRUQsVUFBTSxJQUFJLElBQUksTUFBTSxLQUFLLEtBQUssR0FBRyxDQUFDO0FBRWxDLFVBQU0sU0FBUyxNQUFNO0FBQ25CLGVBQVMsUUFBUSxZQUFZLFdBQVc7QUFJeEMsZUFBUyxjQUFjLEtBQUssSUFBSSxrQkFBa0IsR0FBRyxDQUFDO0FBQUEsSUFDeEQ7QUFFQSxXQUFPO0FBQ1AsV0FBTyxpQkFBaUIsVUFBVSxNQUFNO0FBRXhDLFFBQUksT0FBTztBQUtYLFVBQU0sZ0JBQWdCLFlBQVksSUFBSSxNQUFNO0FBRTVDLFVBQU0sVUFBVSxjQUFjO0FBQUEsTUFDNUIsSUFBSSxJQUFJO0FBQUEsTUFDUjtBQUFBLE1BQ0EsU0FBUyxrQkFBZ0I7QUFDdkIsZ0JBQVE7QUFFUixjQUFNLElBQUksS0FBSztBQUVmLFlBQUksU0FBUyxNQUFNLFFBQVE7QUFDM0IsWUFBSSxTQUFTLE9BQU8sUUFBUSxFQUFFO0FBQzlCLFlBQUksU0FBUyxRQUFRLFFBQVEsRUFBRTtBQUMvQixZQUFJLFNBQVMsV0FBVyxRQUFRLEVBQUU7QUFDbEMsWUFBSSxTQUFTLFVBQVUsUUFBUSxFQUFFO0FBQ2pDLFlBQUksU0FBUyxPQUFPLFFBQVEsRUFBRTtBQUM5QixZQUFJLFNBQVMsT0FBTyxNQUFNLElBQUksRUFBRSxLQUFLO0FBRXJDLGlCQUFTLE9BQU8sT0FBTyxNQUFNO0FBQUEsTUFDL0I7QUFBQSxJQUNGLENBQUM7QUFFRCxXQUFPLE1BQU07QUFDWCxhQUFPLG9CQUFvQixVQUFVLE1BQU07QUFDM0MsY0FBUTtBQUVSLFVBQUksUUFBUTtBQUNaLFVBQUksUUFBUTtBQUNaLGVBQVMsUUFBUTtBQUFBLElBQ25CO0FBQUEsRUFFRixHQUFHLENBQUMsU0FBUyxPQUFPLENBQUM7QUFFckIsTUFBSSxDQUFDLFNBQVM7QUFDWixXQUFPO0FBQUEsRUFDVDtBQUVBLFNBQ0U7QUFBQSxJQUFDO0FBQUE7QUFBQSxNQUNDLFdBQVcsR0FBRyxpQkFBaUIsU0FBUztBQUFBLE1BQ3hDO0FBQUEsTUFDQSxPQUFPO0FBQUEsUUFDTCxjQUFjLEVBQUU7QUFBQSxRQUNoQixHQUFHO0FBQUEsTUFDTDtBQUFBO0FBQUEsRUFDRjtBQUVKOyIsCiAgIm5hbWVzIjogW10KfQo=
