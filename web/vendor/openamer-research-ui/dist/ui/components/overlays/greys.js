"use client";
import { jsx } from "react/jsx-runtime";
import { useEffect, useRef, useState } from "react";
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
const sourceFrag = (
  /*glsl*/
  `
  uniform sampler2D uTex0, uTex1, uTex2, uTex3;
  uniform float uTime, uZoom, uSpeed, uRotate, uFolds, uDrift;
  varying vec2 vUv;

  vec3 gray(vec3 c) { return vec3(dot(c, vec3(.299, .587, .114))); }
  vec2 rot(vec2 p, float a) { return vec2(p.x * cos(a) - p.y * sin(a), p.x * sin(a) + p.y * cos(a)); }

  vec2 kaleid(vec2 p, float n) {
    float a = mod(atan(p.y, p.x), 6.28318 / n) - 3.14159 / n;
    return length(p) * vec2(cos(a), sin(a));
  }

  vec4 tex(int i, vec2 uv) {
    if (i == 0) return texture2D(uTex0, uv);
    if (i == 1) return texture2D(uTex1, uv);
    if (i == 2) return texture2D(uTex2, uv);
    return texture2D(uTex3, uv);
  }

  void main() {
    vec2 uv = rot(vUv - .5, uTime * uRotate * .05);
    if (uFolds > 1.) uv = kaleid(uv, uFolds);

    float dt = uTime * uDrift * .1;
    uv = uv / uZoom + .5 + vec2(sin(dt * .7) * cos(dt * .3), cos(dt * .5) * sin(dt * .9)) * .15 * uDrift;

    float cycle = mod(uTime * uSpeed * .01, 4.);
    int i0 = int(floor(cycle)), i1 = int(mod(float(i0) + 1., 4.));
    float t = smoothstep(0., 1., fract(cycle));

    vec3 base = mix(gray(vec3(1.) - tex(i0, uv).rgb), gray(vec3(1.) - tex(i1, uv).rgb), t);
    vec2 uvF = vec2(1. - uv.x, uv.y);
    vec3 flip = mix(gray(vec3(1.) - tex(i0, uvF).rgb), gray(vec3(1.) - tex(i1, uvF).rgb), t);

    gl_FragColor = vec4(mix(base, flip, .3 + sin(uTime * .2) * .2), 1.);
  }
`
);
const moshFrag = (
  /*glsl*/
  `
  uniform sampler2D uCurrent, uPrev, uTex0, uTex1, uTex2, uTex3;
  uniform float uTime, uIntensity, uMotion, uZoom, uSpeed;
  uniform vec2 uRes;
  varying vec2 vUv;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
  vec2 hash2(vec2 p) { return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }

  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p) * fract(p) * (3. - 2. * fract(p));
    return mix(mix(hash(i), hash(i + vec2(1., 0.)), f.x), mix(hash(i + vec2(0., 1.)), hash(i + vec2(1., 1.)), f.x), f.y);
  }

  vec3 gray(vec3 c) { return vec3(dot(c, vec3(.299, .587, .114))); }

  vec2 distort(vec2 uv, float k, float t) {
    float n1 = noise(uv * 8. + t * .5), n2 = noise(uv * 12. + t * .7), flow = noise(uv * 4. + t * .3);
    return uv + vec2(cos(n1 * 6.28 + t * 1.2), sin(n2 * 6.28 + t * .9)) * .02 * k
             + vec2(cos(flow * 6.28 + uv.y * 10.), sin(flow * 6.28 + uv.x * 10.)) * .015 * k;
  }

  vec3 tex(int i, vec2 uv) {
    vec2 zuv = (uv - .5) / uZoom + .5;
    if (i == 0) return gray(vec3(1.) - texture2D(uTex0, zuv).rgb);
    if (i == 1) return gray(vec3(1.) - texture2D(uTex1, zuv).rgb);
    if (i == 2) return gray(vec3(1.) - texture2D(uTex2, zuv).rgb);
    return gray(vec3(1.) - texture2D(uTex3, zuv).rgb);
  }

  void main() {
    vec2 uv = vUv;
    float t = uTime * uSpeed, tS = floor(t * .1), pS = 80.;
    float amt = uIntensity * uMotion * .8 * (.7 + (sin(t * .5) * .5 + .5) * .3);

    vec2 mUV = distort(uv, uIntensity * .4, t);

    float hS = floor(uv.y * pS), hA = smoothstep(0., .8, hash(vec2(hS, tS)));
    float hO = (hash(vec2(hS, tS + 50.)) - .5) * .25 * hA * amt;
    float vS = floor(uv.x * pS), vA = smoothstep(0., .8, hash(vec2(vS, tS + 100.)));
    float vO = (hash(vec2(vS, tS + 150.)) - .5) * .25 * vA * amt;
    mUV += vec2(hO, vO);

    float bS = pS * .25;
    float hBA = step(.5, hash(vec2(floor(uv.y * bS), tS + 200.)));
    float hBO = (hash(vec2(floor(uv.y * bS), 200.)) - .5) * .35 * hBA * amt;
    float vBA = step(.5, hash(vec2(floor(uv.x * bS), tS + 300.)));
    float vBO = (hash(vec2(floor(uv.x * bS), 250.)) - .5) * .35 * vBA * amt;
    mUV += vec2(hBO, vBO);

    vec2 blk = floor(uv * pS * .15);
    mUV += (hash2(vec2(blk.x, blk.y + 500.)) - .5) * .4 * step(.7, hash(vec2(blk.x, blk.y + tS))) * amt;
    mUV = clamp(mUV, 0., 1.);

    vec3 prev = texture2D(uPrev, mUV).rgb;
    prev = mix(prev, texture2D(uPrev, clamp(uv + vec2(hBO, vBO), 0., 1.)).rgb, max(hBA, vBA) * .9);

    float tY = floor(uv.y * pS * .4);
    if (hash(vec2(tY, tS + 400.)) > .75) {
      prev = mix(prev, texture2D(uPrev, clamp(vec2(uv.x + (hash(vec2(tY, 400.)) - .5) * .5 * amt, uv.y), 0., 1.)).rgb, .85);
    }

    if (hA > 0. && amt > .01) {
      prev = mix(prev, gray(texture2D(uPrev, clamp(vec2(uv.x + (gray(prev).r - uv.x) * amt + hO, uv.y), 0., 1.)).rgb), hA);
    }

    float d = mix(mix(.97, .99, noise(uv * 8. + t * .2)), 0., step(.994, hash(vec2(tS, 0.))));
    gl_FragColor = vec4(mix(texture2D(uCurrent, uv).rgb, prev, d), 1.);
  }
`
);
const outputFrag = (
  /*glsl*/
  `
  uniform sampler2D uInput;
  uniform float uTime, uAlpha, uHue;
  uniform vec3 uColor;
  varying vec2 vUv;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

  vec3 hueShift(vec3 c, float h) {
    float a = h * 6.28318, s = sin(a), co = cos(a);
    vec3 w = vec3(.299, .587, .114);
    return clamp(vec3(
      dot(c, w) + dot(c, vec3(.701, -.587, -.114) * co + vec3(.168, .330, -.497) * s),
      dot(c, w) + dot(c, vec3(-.299, .413, -.114) * co + vec3(.328, .035, -.363) * s),
      dot(c, w) + dot(c, vec3(-.299, -.587, .886) * co + vec3(-.497, .330, .168) * s)
    ), 0., 1.);
  }

  void main() {
    vec3 m = texture2D(uInput, vUv).rgb;
    m *= 1. - step(.5, fract(vUv.y * 200.)) * .06 * step(.97, hash(vec2(floor(vUv.y * 30.), floor(uTime * .5))));

    float lum = dot(m, vec3(.299, .587, .114));
    gl_FragColor = vec4(hueShift(mix(vec3(lum), uColor * lum * 2., length(uColor)), uHue) * uAlpha, smoothstep(.08, .18, lum * uAlpha));
  }
`
);
const TEXTURES = [
  "/anatomy/grays-0.jpg",
  "/anatomy/grays-3.jpg",
  "/anatomy/grays-6.jpg",
  "/anatomy/grays-9.jpg"
];
export function Greys({ className, style }) {
  const gpuTier = useGpuTier();
  const [blendOverride, setBlendOverride] = useState(null);
  const canvasRef = useRef(null);
  const c = useSmoothControls(
    "Effects/Greys",
    {
      alpha: { max: 1, min: 0, step: 0.01, value: 0.19 },
      blend: { options: BLEND_MODES, value: "color-burn" },
      color: { value: "#ffac02" },
      drift: { max: 2, min: 0, step: 0.1, value: 0.5 },
      enabled: { value: false },
      folds: { max: 12, min: 1, step: 1, value: 1 },
      hue: { max: 1, min: 0, step: 0.01, value: 0.37 },
      intensity: { max: 3, min: 0, step: 0.1, value: 0.1 },
      motion: { max: 2, min: 0, step: 0.1, value: 0.1 },
      rotate: { max: 2, min: -2, step: 0.1, value: 0.3 },
      speed: { max: 1, min: 0.01, step: 0.01, value: 0.21 },
      zoom: { max: 4, min: 0.5, step: 0.1, value: 0.7 }
    },
    { collapsed: true }
  );
  const cRef = useRef(c);
  cRef.current = c;
  useEffect(() => {
    const onKey = (e) => e.key.toLowerCase() === "x" && setBlendOverride((p) => p === "screen" ? null : "screen");
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const enabled = c.enabled && gpuTier === 2;
  useEffect(() => {
    if (!canvasRef.current || !enabled) {
      return;
    }
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        canvas: canvasRef.current
      });
    } catch {
      $gpuTier.set(0);
      return;
    }
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const geo = new THREE.PlaneGeometry(2, 2);
    const [rtSource, rtA, rtB] = [0, 1, 2].map(
      () => new THREE.WebGLRenderTarget(innerWidth, innerHeight, {
        magFilter: THREE.NearestFilter,
        minFilter: THREE.NearestFilter
      })
    );
    const textures = TEXTURES.map((p) => {
      const t = new THREE.TextureLoader().load(p);
      t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
      t.minFilter = t.magFilter = THREE.LinearFilter;
      return t;
    });
    const texU = Object.fromEntries(
      textures.map((t, i) => [`uTex${i}`, { value: t }])
    );
    const srcU = {
      ...texU,
      uDrift: { value: 0 },
      uFolds: { value: 0 },
      uRotate: { value: 0 },
      uSpeed: { value: 0 },
      uTime: { value: 0 },
      uZoom: { value: 0 }
    };
    const moshU = {
      ...texU,
      uCurrent: { value: rtSource.texture },
      uIntensity: { value: 0 },
      uMotion: { value: 0 },
      uPrev: { value: rtA.texture },
      uRes: { value: new THREE.Vector2(innerWidth, innerHeight) },
      uSpeed: { value: 0 },
      uTime: { value: 0 },
      uZoom: { value: 0 }
    };
    const outU = {
      uAlpha: { value: 0 },
      uColor: { value: new THREE.Color() },
      uHue: { value: 0 },
      uInput: { value: rtB.texture },
      uTime: { value: 0 }
    };
    const mkScene = (frag, uniforms, transparent = false) => {
      const s = new THREE.Scene();
      s.add(
        new THREE.Mesh(
          geo.clone(),
          new THREE.ShaderMaterial({
            fragmentShader: frag,
            transparent,
            uniforms,
            vertexShader: vert
          })
        )
      );
      return s;
    };
    const srcScene = mkScene(sourceFrag, srcU);
    const moshScene = mkScene(moshFrag, moshU);
    const outScene = mkScene(outputFrag, outU, true);
    const resize = () => {
      renderer.setSize(innerWidth, innerHeight);
      renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
      [rtSource, rtA, rtB].forEach((rt) => rt.setSize(innerWidth, innerHeight));
      moshU.uRes.value.set(innerWidth, innerHeight);
    };
    resize();
    window.addEventListener("resize", resize);
    let ping = true, time = 0;
    const dispose = runRenderLoop({
      el: canvasRef.current,
      minIntervalMs: 33,
      onFrame: (deltaSeconds) => {
        time += deltaSeconds;
        const v = cRef.current;
        srcU.uTime.value = time;
        srcU.uSpeed.value = v.speed;
        srcU.uZoom.value = v.zoom;
        srcU.uRotate.value = v.rotate;
        srcU.uFolds.value = v.folds;
        srcU.uDrift.value = v.drift;
        moshU.uTime.value = time;
        moshU.uIntensity.value = v.intensity;
        moshU.uMotion.value = v.motion;
        moshU.uSpeed.value = v.speed;
        moshU.uZoom.value = v.zoom;
        outU.uTime.value = time;
        outU.uAlpha.value = v.alpha;
        outU.uHue.value = v.hue;
        outU.uColor.value.set(typeof v.color === "string" ? v.color : "#fff");
        renderer.setRenderTarget(rtSource);
        renderer.render(srcScene, camera);
        const [read, write] = ping ? [rtA, rtB] : [rtB, rtA];
        moshU.uPrev.value = read.texture;
        renderer.setRenderTarget(write);
        renderer.render(moshScene, camera);
        outU.uInput.value = write.texture;
        renderer.setRenderTarget(null);
        renderer.render(outScene, camera);
        ping = !ping;
      }
    });
    return () => {
      window.removeEventListener("resize", resize);
      dispose();
      textures.forEach((t) => t.dispose());
      [geo, rtSource, rtA, rtB, renderer].forEach((x) => x.dispose());
    };
  }, [enabled]);
  if (!enabled) {
    return null;
  }
  return /* @__PURE__ */ jsx(
    "canvas",
    {
      className: cn("h-full w-full", className),
      ref: canvasRef,
      style: {
        mixBlendMode: blendOverride ?? c.blend,
        ...style
      }
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZUVmZmVjdCwgdXNlUmVmLCB1c2VTdGF0ZSB9IGZyb20gJ3JlYWN0J1xuaW1wb3J0ICogYXMgVEhSRUUgZnJvbSAndGhyZWUnXG5cbmltcG9ydCB7ICRncHVUaWVyLCB1c2VHcHVUaWVyIH0gZnJvbSAnLi4vLi4vLi4vaG9va3MvdXNlLWdwdS10aWVyJ1xuaW1wb3J0IHsgcnVuUmVuZGVyTG9vcCB9IGZyb20gJy4uLy4uLy4uL2hvb2tzL3VzZS1yZW5kZXItbG9vcCdcbmltcG9ydCB7IHVzZVNtb290aENvbnRyb2xzIH0gZnJvbSAnLi4vLi4vLi4vaG9va3MvdXNlLXNtb290aC1jb250cm9scydcbmltcG9ydCB7IGNuIH0gZnJvbSAnLi4vLi4vLi4vdXRpbHMnXG5cbmltcG9ydCB7IEJMRU5EX01PREVTIH0gZnJvbSAnLi9ibGVuZC1tb2RlcydcblxuY29uc3QgdmVydCA9IC8qZ2xzbCovIGBcbiAgdmFyeWluZyB2ZWMyIHZVdjtcbiAgdm9pZCBtYWluKCkge1xuICAgIHZVdiA9IHV2O1xuICAgIGdsX1Bvc2l0aW9uID0gcHJvamVjdGlvbk1hdHJpeCAqIG1vZGVsVmlld01hdHJpeCAqIHZlYzQocG9zaXRpb24sIDEuMCk7XG4gIH1cbmBcblxuY29uc3Qgc291cmNlRnJhZyA9IC8qZ2xzbCovIGBcbiAgdW5pZm9ybSBzYW1wbGVyMkQgdVRleDAsIHVUZXgxLCB1VGV4MiwgdVRleDM7XG4gIHVuaWZvcm0gZmxvYXQgdVRpbWUsIHVab29tLCB1U3BlZWQsIHVSb3RhdGUsIHVGb2xkcywgdURyaWZ0O1xuICB2YXJ5aW5nIHZlYzIgdlV2O1xuXG4gIHZlYzMgZ3JheSh2ZWMzIGMpIHsgcmV0dXJuIHZlYzMoZG90KGMsIHZlYzMoLjI5OSwgLjU4NywgLjExNCkpKTsgfVxuICB2ZWMyIHJvdCh2ZWMyIHAsIGZsb2F0IGEpIHsgcmV0dXJuIHZlYzIocC54ICogY29zKGEpIC0gcC55ICogc2luKGEpLCBwLnggKiBzaW4oYSkgKyBwLnkgKiBjb3MoYSkpOyB9XG5cbiAgdmVjMiBrYWxlaWQodmVjMiBwLCBmbG9hdCBuKSB7XG4gICAgZmxvYXQgYSA9IG1vZChhdGFuKHAueSwgcC54KSwgNi4yODMxOCAvIG4pIC0gMy4xNDE1OSAvIG47XG4gICAgcmV0dXJuIGxlbmd0aChwKSAqIHZlYzIoY29zKGEpLCBzaW4oYSkpO1xuICB9XG5cbiAgdmVjNCB0ZXgoaW50IGksIHZlYzIgdXYpIHtcbiAgICBpZiAoaSA9PSAwKSByZXR1cm4gdGV4dHVyZTJEKHVUZXgwLCB1dik7XG4gICAgaWYgKGkgPT0gMSkgcmV0dXJuIHRleHR1cmUyRCh1VGV4MSwgdXYpO1xuICAgIGlmIChpID09IDIpIHJldHVybiB0ZXh0dXJlMkQodVRleDIsIHV2KTtcbiAgICByZXR1cm4gdGV4dHVyZTJEKHVUZXgzLCB1dik7XG4gIH1cblxuICB2b2lkIG1haW4oKSB7XG4gICAgdmVjMiB1diA9IHJvdCh2VXYgLSAuNSwgdVRpbWUgKiB1Um90YXRlICogLjA1KTtcbiAgICBpZiAodUZvbGRzID4gMS4pIHV2ID0ga2FsZWlkKHV2LCB1Rm9sZHMpO1xuXG4gICAgZmxvYXQgZHQgPSB1VGltZSAqIHVEcmlmdCAqIC4xO1xuICAgIHV2ID0gdXYgLyB1Wm9vbSArIC41ICsgdmVjMihzaW4oZHQgKiAuNykgKiBjb3MoZHQgKiAuMyksIGNvcyhkdCAqIC41KSAqIHNpbihkdCAqIC45KSkgKiAuMTUgKiB1RHJpZnQ7XG5cbiAgICBmbG9hdCBjeWNsZSA9IG1vZCh1VGltZSAqIHVTcGVlZCAqIC4wMSwgNC4pO1xuICAgIGludCBpMCA9IGludChmbG9vcihjeWNsZSkpLCBpMSA9IGludChtb2QoZmxvYXQoaTApICsgMS4sIDQuKSk7XG4gICAgZmxvYXQgdCA9IHNtb290aHN0ZXAoMC4sIDEuLCBmcmFjdChjeWNsZSkpO1xuXG4gICAgdmVjMyBiYXNlID0gbWl4KGdyYXkodmVjMygxLikgLSB0ZXgoaTAsIHV2KS5yZ2IpLCBncmF5KHZlYzMoMS4pIC0gdGV4KGkxLCB1dikucmdiKSwgdCk7XG4gICAgdmVjMiB1dkYgPSB2ZWMyKDEuIC0gdXYueCwgdXYueSk7XG4gICAgdmVjMyBmbGlwID0gbWl4KGdyYXkodmVjMygxLikgLSB0ZXgoaTAsIHV2RikucmdiKSwgZ3JheSh2ZWMzKDEuKSAtIHRleChpMSwgdXZGKS5yZ2IpLCB0KTtcblxuICAgIGdsX0ZyYWdDb2xvciA9IHZlYzQobWl4KGJhc2UsIGZsaXAsIC4zICsgc2luKHVUaW1lICogLjIpICogLjIpLCAxLik7XG4gIH1cbmBcblxuY29uc3QgbW9zaEZyYWcgPSAvKmdsc2wqLyBgXG4gIHVuaWZvcm0gc2FtcGxlcjJEIHVDdXJyZW50LCB1UHJldiwgdVRleDAsIHVUZXgxLCB1VGV4MiwgdVRleDM7XG4gIHVuaWZvcm0gZmxvYXQgdVRpbWUsIHVJbnRlbnNpdHksIHVNb3Rpb24sIHVab29tLCB1U3BlZWQ7XG4gIHVuaWZvcm0gdmVjMiB1UmVzO1xuICB2YXJ5aW5nIHZlYzIgdlV2O1xuXG4gIGZsb2F0IGhhc2godmVjMiBwKSB7IHJldHVybiBmcmFjdChzaW4oZG90KHAsIHZlYzIoMTIuOTg5OCwgNzguMjMzKSkpICogNDM3NTguNTQ1Myk7IH1cbiAgdmVjMiBoYXNoMih2ZWMyIHApIHsgcmV0dXJuIGZyYWN0KHNpbih2ZWMyKGRvdChwLCB2ZWMyKDEyNy4xLCAzMTEuNykpLCBkb3QocCwgdmVjMigyNjkuNSwgMTgzLjMpKSkpICogNDM3NTguNTQ1Myk7IH1cblxuICBmbG9hdCBub2lzZSh2ZWMyIHApIHtcbiAgICB2ZWMyIGkgPSBmbG9vcihwKSwgZiA9IGZyYWN0KHApICogZnJhY3QocCkgKiAoMy4gLSAyLiAqIGZyYWN0KHApKTtcbiAgICByZXR1cm4gbWl4KG1peChoYXNoKGkpLCBoYXNoKGkgKyB2ZWMyKDEuLCAwLikpLCBmLngpLCBtaXgoaGFzaChpICsgdmVjMigwLiwgMS4pKSwgaGFzaChpICsgdmVjMigxLiwgMS4pKSwgZi54KSwgZi55KTtcbiAgfVxuXG4gIHZlYzMgZ3JheSh2ZWMzIGMpIHsgcmV0dXJuIHZlYzMoZG90KGMsIHZlYzMoLjI5OSwgLjU4NywgLjExNCkpKTsgfVxuXG4gIHZlYzIgZGlzdG9ydCh2ZWMyIHV2LCBmbG9hdCBrLCBmbG9hdCB0KSB7XG4gICAgZmxvYXQgbjEgPSBub2lzZSh1diAqIDguICsgdCAqIC41KSwgbjIgPSBub2lzZSh1diAqIDEyLiArIHQgKiAuNyksIGZsb3cgPSBub2lzZSh1diAqIDQuICsgdCAqIC4zKTtcbiAgICByZXR1cm4gdXYgKyB2ZWMyKGNvcyhuMSAqIDYuMjggKyB0ICogMS4yKSwgc2luKG4yICogNi4yOCArIHQgKiAuOSkpICogLjAyICoga1xuICAgICAgICAgICAgICsgdmVjMihjb3MoZmxvdyAqIDYuMjggKyB1di55ICogMTAuKSwgc2luKGZsb3cgKiA2LjI4ICsgdXYueCAqIDEwLikpICogLjAxNSAqIGs7XG4gIH1cblxuICB2ZWMzIHRleChpbnQgaSwgdmVjMiB1dikge1xuICAgIHZlYzIgenV2ID0gKHV2IC0gLjUpIC8gdVpvb20gKyAuNTtcbiAgICBpZiAoaSA9PSAwKSByZXR1cm4gZ3JheSh2ZWMzKDEuKSAtIHRleHR1cmUyRCh1VGV4MCwgenV2KS5yZ2IpO1xuICAgIGlmIChpID09IDEpIHJldHVybiBncmF5KHZlYzMoMS4pIC0gdGV4dHVyZTJEKHVUZXgxLCB6dXYpLnJnYik7XG4gICAgaWYgKGkgPT0gMikgcmV0dXJuIGdyYXkodmVjMygxLikgLSB0ZXh0dXJlMkQodVRleDIsIHp1dikucmdiKTtcbiAgICByZXR1cm4gZ3JheSh2ZWMzKDEuKSAtIHRleHR1cmUyRCh1VGV4MywgenV2KS5yZ2IpO1xuICB9XG5cbiAgdm9pZCBtYWluKCkge1xuICAgIHZlYzIgdXYgPSB2VXY7XG4gICAgZmxvYXQgdCA9IHVUaW1lICogdVNwZWVkLCB0UyA9IGZsb29yKHQgKiAuMSksIHBTID0gODAuO1xuICAgIGZsb2F0IGFtdCA9IHVJbnRlbnNpdHkgKiB1TW90aW9uICogLjggKiAoLjcgKyAoc2luKHQgKiAuNSkgKiAuNSArIC41KSAqIC4zKTtcblxuICAgIHZlYzIgbVVWID0gZGlzdG9ydCh1diwgdUludGVuc2l0eSAqIC40LCB0KTtcblxuICAgIGZsb2F0IGhTID0gZmxvb3IodXYueSAqIHBTKSwgaEEgPSBzbW9vdGhzdGVwKDAuLCAuOCwgaGFzaCh2ZWMyKGhTLCB0UykpKTtcbiAgICBmbG9hdCBoTyA9IChoYXNoKHZlYzIoaFMsIHRTICsgNTAuKSkgLSAuNSkgKiAuMjUgKiBoQSAqIGFtdDtcbiAgICBmbG9hdCB2UyA9IGZsb29yKHV2LnggKiBwUyksIHZBID0gc21vb3Roc3RlcCgwLiwgLjgsIGhhc2godmVjMih2UywgdFMgKyAxMDAuKSkpO1xuICAgIGZsb2F0IHZPID0gKGhhc2godmVjMih2UywgdFMgKyAxNTAuKSkgLSAuNSkgKiAuMjUgKiB2QSAqIGFtdDtcbiAgICBtVVYgKz0gdmVjMihoTywgdk8pO1xuXG4gICAgZmxvYXQgYlMgPSBwUyAqIC4yNTtcbiAgICBmbG9hdCBoQkEgPSBzdGVwKC41LCBoYXNoKHZlYzIoZmxvb3IodXYueSAqIGJTKSwgdFMgKyAyMDAuKSkpO1xuICAgIGZsb2F0IGhCTyA9IChoYXNoKHZlYzIoZmxvb3IodXYueSAqIGJTKSwgMjAwLikpIC0gLjUpICogLjM1ICogaEJBICogYW10O1xuICAgIGZsb2F0IHZCQSA9IHN0ZXAoLjUsIGhhc2godmVjMihmbG9vcih1di54ICogYlMpLCB0UyArIDMwMC4pKSk7XG4gICAgZmxvYXQgdkJPID0gKGhhc2godmVjMihmbG9vcih1di54ICogYlMpLCAyNTAuKSkgLSAuNSkgKiAuMzUgKiB2QkEgKiBhbXQ7XG4gICAgbVVWICs9IHZlYzIoaEJPLCB2Qk8pO1xuXG4gICAgdmVjMiBibGsgPSBmbG9vcih1diAqIHBTICogLjE1KTtcbiAgICBtVVYgKz0gKGhhc2gyKHZlYzIoYmxrLngsIGJsay55ICsgNTAwLikpIC0gLjUpICogLjQgKiBzdGVwKC43LCBoYXNoKHZlYzIoYmxrLngsIGJsay55ICsgdFMpKSkgKiBhbXQ7XG4gICAgbVVWID0gY2xhbXAobVVWLCAwLiwgMS4pO1xuXG4gICAgdmVjMyBwcmV2ID0gdGV4dHVyZTJEKHVQcmV2LCBtVVYpLnJnYjtcbiAgICBwcmV2ID0gbWl4KHByZXYsIHRleHR1cmUyRCh1UHJldiwgY2xhbXAodXYgKyB2ZWMyKGhCTywgdkJPKSwgMC4sIDEuKSkucmdiLCBtYXgoaEJBLCB2QkEpICogLjkpO1xuXG4gICAgZmxvYXQgdFkgPSBmbG9vcih1di55ICogcFMgKiAuNCk7XG4gICAgaWYgKGhhc2godmVjMih0WSwgdFMgKyA0MDAuKSkgPiAuNzUpIHtcbiAgICAgIHByZXYgPSBtaXgocHJldiwgdGV4dHVyZTJEKHVQcmV2LCBjbGFtcCh2ZWMyKHV2LnggKyAoaGFzaCh2ZWMyKHRZLCA0MDAuKSkgLSAuNSkgKiAuNSAqIGFtdCwgdXYueSksIDAuLCAxLikpLnJnYiwgLjg1KTtcbiAgICB9XG5cbiAgICBpZiAoaEEgPiAwLiAmJiBhbXQgPiAuMDEpIHtcbiAgICAgIHByZXYgPSBtaXgocHJldiwgZ3JheSh0ZXh0dXJlMkQodVByZXYsIGNsYW1wKHZlYzIodXYueCArIChncmF5KHByZXYpLnIgLSB1di54KSAqIGFtdCArIGhPLCB1di55KSwgMC4sIDEuKSkucmdiKSwgaEEpO1xuICAgIH1cblxuICAgIGZsb2F0IGQgPSBtaXgobWl4KC45NywgLjk5LCBub2lzZSh1diAqIDguICsgdCAqIC4yKSksIDAuLCBzdGVwKC45OTQsIGhhc2godmVjMih0UywgMC4pKSkpO1xuICAgIGdsX0ZyYWdDb2xvciA9IHZlYzQobWl4KHRleHR1cmUyRCh1Q3VycmVudCwgdXYpLnJnYiwgcHJldiwgZCksIDEuKTtcbiAgfVxuYFxuXG5jb25zdCBvdXRwdXRGcmFnID0gLypnbHNsKi8gYFxuICB1bmlmb3JtIHNhbXBsZXIyRCB1SW5wdXQ7XG4gIHVuaWZvcm0gZmxvYXQgdVRpbWUsIHVBbHBoYSwgdUh1ZTtcbiAgdW5pZm9ybSB2ZWMzIHVDb2xvcjtcbiAgdmFyeWluZyB2ZWMyIHZVdjtcblxuICBmbG9hdCBoYXNoKHZlYzIgcCkgeyByZXR1cm4gZnJhY3Qoc2luKGRvdChwLCB2ZWMyKDEyNy4xLCAzMTEuNykpKSAqIDQzNzU4LjU0NTMpOyB9XG5cbiAgdmVjMyBodWVTaGlmdCh2ZWMzIGMsIGZsb2F0IGgpIHtcbiAgICBmbG9hdCBhID0gaCAqIDYuMjgzMTgsIHMgPSBzaW4oYSksIGNvID0gY29zKGEpO1xuICAgIHZlYzMgdyA9IHZlYzMoLjI5OSwgLjU4NywgLjExNCk7XG4gICAgcmV0dXJuIGNsYW1wKHZlYzMoXG4gICAgICBkb3QoYywgdykgKyBkb3QoYywgdmVjMyguNzAxLCAtLjU4NywgLS4xMTQpICogY28gKyB2ZWMzKC4xNjgsIC4zMzAsIC0uNDk3KSAqIHMpLFxuICAgICAgZG90KGMsIHcpICsgZG90KGMsIHZlYzMoLS4yOTksIC40MTMsIC0uMTE0KSAqIGNvICsgdmVjMyguMzI4LCAuMDM1LCAtLjM2MykgKiBzKSxcbiAgICAgIGRvdChjLCB3KSArIGRvdChjLCB2ZWMzKC0uMjk5LCAtLjU4NywgLjg4NikgKiBjbyArIHZlYzMoLS40OTcsIC4zMzAsIC4xNjgpICogcylcbiAgICApLCAwLiwgMS4pO1xuICB9XG5cbiAgdm9pZCBtYWluKCkge1xuICAgIHZlYzMgbSA9IHRleHR1cmUyRCh1SW5wdXQsIHZVdikucmdiO1xuICAgIG0gKj0gMS4gLSBzdGVwKC41LCBmcmFjdCh2VXYueSAqIDIwMC4pKSAqIC4wNiAqIHN0ZXAoLjk3LCBoYXNoKHZlYzIoZmxvb3IodlV2LnkgKiAzMC4pLCBmbG9vcih1VGltZSAqIC41KSkpKTtcblxuICAgIGZsb2F0IGx1bSA9IGRvdChtLCB2ZWMzKC4yOTksIC41ODcsIC4xMTQpKTtcbiAgICBnbF9GcmFnQ29sb3IgPSB2ZWM0KGh1ZVNoaWZ0KG1peCh2ZWMzKGx1bSksIHVDb2xvciAqIGx1bSAqIDIuLCBsZW5ndGgodUNvbG9yKSksIHVIdWUpICogdUFscGhhLCBzbW9vdGhzdGVwKC4wOCwgLjE4LCBsdW0gKiB1QWxwaGEpKTtcbiAgfVxuYFxuXG5jb25zdCBURVhUVVJFUyA9IFtcbiAgJy9hbmF0b215L2dyYXlzLTAuanBnJyxcbiAgJy9hbmF0b215L2dyYXlzLTMuanBnJyxcbiAgJy9hbmF0b215L2dyYXlzLTYuanBnJyxcbiAgJy9hbmF0b215L2dyYXlzLTkuanBnJ1xuXVxuXG5leHBvcnQgZnVuY3Rpb24gR3JleXMoeyBjbGFzc05hbWUsIHN0eWxlIH06IEdyZXlzUHJvcHMpIHtcbiAgY29uc3QgZ3B1VGllciA9IHVzZUdwdVRpZXIoKVxuICBjb25zdCBbYmxlbmRPdmVycmlkZSwgc2V0QmxlbmRPdmVycmlkZV0gPSB1c2VTdGF0ZTxzdHJpbmcgfCBudWxsPihudWxsKVxuICBjb25zdCBjYW52YXNSZWYgPSB1c2VSZWY8SFRNTENhbnZhc0VsZW1lbnQ+KG51bGwpXG5cbiAgY29uc3QgYyA9IHVzZVNtb290aENvbnRyb2xzKFxuICAgICdFZmZlY3RzL0dyZXlzJyxcbiAgICB7XG4gICAgICBhbHBoYTogeyBtYXg6IDEsIG1pbjogMCwgc3RlcDogMC4wMSwgdmFsdWU6IDAuMTkgfSxcbiAgICAgIGJsZW5kOiB7IG9wdGlvbnM6IEJMRU5EX01PREVTLCB2YWx1ZTogJ2NvbG9yLWJ1cm4nIH0sXG4gICAgICBjb2xvcjogeyB2YWx1ZTogJyNmZmFjMDInIH0sXG4gICAgICBkcmlmdDogeyBtYXg6IDIsIG1pbjogMCwgc3RlcDogMC4xLCB2YWx1ZTogMC41IH0sXG4gICAgICBlbmFibGVkOiB7IHZhbHVlOiBmYWxzZSB9LFxuICAgICAgZm9sZHM6IHsgbWF4OiAxMiwgbWluOiAxLCBzdGVwOiAxLCB2YWx1ZTogMSB9LFxuICAgICAgaHVlOiB7IG1heDogMSwgbWluOiAwLCBzdGVwOiAwLjAxLCB2YWx1ZTogMC4zNyB9LFxuICAgICAgaW50ZW5zaXR5OiB7IG1heDogMywgbWluOiAwLCBzdGVwOiAwLjEsIHZhbHVlOiAwLjEgfSxcbiAgICAgIG1vdGlvbjogeyBtYXg6IDIsIG1pbjogMCwgc3RlcDogMC4xLCB2YWx1ZTogMC4xIH0sXG4gICAgICByb3RhdGU6IHsgbWF4OiAyLCBtaW46IC0yLCBzdGVwOiAwLjEsIHZhbHVlOiAwLjMgfSxcbiAgICAgIHNwZWVkOiB7IG1heDogMSwgbWluOiAwLjAxLCBzdGVwOiAwLjAxLCB2YWx1ZTogMC4yMSB9LFxuICAgICAgem9vbTogeyBtYXg6IDQsIG1pbjogMC41LCBzdGVwOiAwLjEsIHZhbHVlOiAwLjcgfVxuICAgIH0sXG4gICAgeyBjb2xsYXBzZWQ6IHRydWUgfVxuICApXG5cbiAgY29uc3QgY1JlZiA9IHVzZVJlZihjKVxuICBjUmVmLmN1cnJlbnQgPSBjXG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBjb25zdCBvbktleSA9IChlOiBLZXlib2FyZEV2ZW50KSA9PlxuICAgICAgZS5rZXkudG9Mb3dlckNhc2UoKSA9PT0gJ3gnICYmXG4gICAgICBzZXRCbGVuZE92ZXJyaWRlKHAgPT4gKHAgPT09ICdzY3JlZW4nID8gbnVsbCA6ICdzY3JlZW4nKSlcblxuICAgIHdpbmRvdy5hZGRFdmVudExpc3RlbmVyKCdrZXlkb3duJywgb25LZXkpXG5cbiAgICByZXR1cm4gKCkgPT4gd2luZG93LnJlbW92ZUV2ZW50TGlzdGVuZXIoJ2tleWRvd24nLCBvbktleSlcbiAgfSwgW10pXG5cbiAgY29uc3QgZW5hYmxlZCA9IGMuZW5hYmxlZCAmJiBncHVUaWVyID09PSAyXG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBpZiAoIWNhbnZhc1JlZi5jdXJyZW50IHx8ICFlbmFibGVkKSB7XG4gICAgICByZXR1cm5cbiAgICB9XG5cbiAgICBsZXQgcmVuZGVyZXI6IFRIUkVFLldlYkdMUmVuZGVyZXJcblxuICAgIHRyeSB7XG4gICAgICByZW5kZXJlciA9IG5ldyBUSFJFRS5XZWJHTFJlbmRlcmVyKHtcbiAgICAgICAgYWxwaGE6IHRydWUsXG4gICAgICAgIGNhbnZhczogY2FudmFzUmVmLmN1cnJlbnRcbiAgICAgIH0pXG4gICAgfSBjYXRjaCB7XG4gICAgICAvLyBTZWUgbm90ZSBpbiBub2lzZS50c3ggXHUyMDE0IGVhZ2VyIGdwdS10aWVyIGRldGVjdGlvbiBzaG91bGQga2VlcCB1c1xuICAgICAgLy8gb3V0IG9mIGhlcmUsIGJ1dCBpZiB0aGUgZHJpdmVyIGZhaWxzIHRoZSByZW5kZXJlciBjb25zdHJ1Y3RvclxuICAgICAgLy8gYW55d2F5LCBkb3duZ3JhZGUgc28gb3RoZXIgb3ZlcmxheXMgc3RvcCB0cnlpbmcgdG9vLlxuICAgICAgJGdwdVRpZXIuc2V0KDApXG5cbiAgICAgIHJldHVyblxuICAgIH1cblxuICAgIGNvbnN0IGNhbWVyYSA9IG5ldyBUSFJFRS5PcnRob2dyYXBoaWNDYW1lcmEoLTEsIDEsIDEsIC0xLCAwLCAxKVxuICAgIGNvbnN0IGdlbyA9IG5ldyBUSFJFRS5QbGFuZUdlb21ldHJ5KDIsIDIpXG5cbiAgICBjb25zdCBbcnRTb3VyY2UsIHJ0QSwgcnRCXSA9IFswLCAxLCAyXS5tYXAoXG4gICAgICAoKSA9PlxuICAgICAgICBuZXcgVEhSRUUuV2ViR0xSZW5kZXJUYXJnZXQoaW5uZXJXaWR0aCwgaW5uZXJIZWlnaHQsIHtcbiAgICAgICAgICBtYWdGaWx0ZXI6IFRIUkVFLk5lYXJlc3RGaWx0ZXIsXG4gICAgICAgICAgbWluRmlsdGVyOiBUSFJFRS5OZWFyZXN0RmlsdGVyXG4gICAgICAgIH0pXG4gICAgKVxuXG4gICAgY29uc3QgdGV4dHVyZXMgPSBURVhUVVJFUy5tYXAocCA9PiB7XG4gICAgICBjb25zdCB0ID0gbmV3IFRIUkVFLlRleHR1cmVMb2FkZXIoKS5sb2FkKHApXG4gICAgICB0LndyYXBTID0gdC53cmFwVCA9IFRIUkVFLkNsYW1wVG9FZGdlV3JhcHBpbmdcbiAgICAgIHQubWluRmlsdGVyID0gdC5tYWdGaWx0ZXIgPSBUSFJFRS5MaW5lYXJGaWx0ZXJcblxuICAgICAgcmV0dXJuIHRcbiAgICB9KVxuXG4gICAgY29uc3QgdGV4VSA9IE9iamVjdC5mcm9tRW50cmllcyhcbiAgICAgIHRleHR1cmVzLm1hcCgodCwgaSkgPT4gW2B1VGV4JHtpfWAsIHsgdmFsdWU6IHQgfV0pXG4gICAgKVxuXG4gICAgY29uc3Qgc3JjVSA9IHtcbiAgICAgIC4uLnRleFUsXG4gICAgICB1RHJpZnQ6IHsgdmFsdWU6IDAgfSxcbiAgICAgIHVGb2xkczogeyB2YWx1ZTogMCB9LFxuICAgICAgdVJvdGF0ZTogeyB2YWx1ZTogMCB9LFxuICAgICAgdVNwZWVkOiB7IHZhbHVlOiAwIH0sXG4gICAgICB1VGltZTogeyB2YWx1ZTogMCB9LFxuICAgICAgdVpvb206IHsgdmFsdWU6IDAgfVxuICAgIH1cblxuICAgIGNvbnN0IG1vc2hVID0ge1xuICAgICAgLi4udGV4VSxcbiAgICAgIHVDdXJyZW50OiB7IHZhbHVlOiBydFNvdXJjZS50ZXh0dXJlIH0sXG4gICAgICB1SW50ZW5zaXR5OiB7IHZhbHVlOiAwIH0sXG4gICAgICB1TW90aW9uOiB7IHZhbHVlOiAwIH0sXG4gICAgICB1UHJldjogeyB2YWx1ZTogcnRBLnRleHR1cmUgfSxcbiAgICAgIHVSZXM6IHsgdmFsdWU6IG5ldyBUSFJFRS5WZWN0b3IyKGlubmVyV2lkdGgsIGlubmVySGVpZ2h0KSB9LFxuICAgICAgdVNwZWVkOiB7IHZhbHVlOiAwIH0sXG4gICAgICB1VGltZTogeyB2YWx1ZTogMCB9LFxuICAgICAgdVpvb206IHsgdmFsdWU6IDAgfVxuICAgIH1cblxuICAgIGNvbnN0IG91dFUgPSB7XG4gICAgICB1QWxwaGE6IHsgdmFsdWU6IDAgfSxcbiAgICAgIHVDb2xvcjogeyB2YWx1ZTogbmV3IFRIUkVFLkNvbG9yKCkgfSxcbiAgICAgIHVIdWU6IHsgdmFsdWU6IDAgfSxcbiAgICAgIHVJbnB1dDogeyB2YWx1ZTogcnRCLnRleHR1cmUgfSxcbiAgICAgIHVUaW1lOiB7IHZhbHVlOiAwIH1cbiAgICB9XG5cbiAgICBjb25zdCBta1NjZW5lID0gKGZyYWc6IHN0cmluZywgdW5pZm9ybXM6IG9iamVjdCwgdHJhbnNwYXJlbnQgPSBmYWxzZSkgPT4ge1xuICAgICAgY29uc3QgcyA9IG5ldyBUSFJFRS5TY2VuZSgpXG4gICAgICBzLmFkZChcbiAgICAgICAgbmV3IFRIUkVFLk1lc2goXG4gICAgICAgICAgZ2VvLmNsb25lKCksXG4gICAgICAgICAgbmV3IFRIUkVFLlNoYWRlck1hdGVyaWFsKHtcbiAgICAgICAgICAgIGZyYWdtZW50U2hhZGVyOiBmcmFnLFxuICAgICAgICAgICAgdHJhbnNwYXJlbnQsXG4gICAgICAgICAgICB1bmlmb3JtczogdW5pZm9ybXMgYXMgUmVjb3JkPHN0cmluZywgVEhSRUUuSVVuaWZvcm08YW55Pj4sXG4gICAgICAgICAgICB2ZXJ0ZXhTaGFkZXI6IHZlcnRcbiAgICAgICAgICB9KVxuICAgICAgICApXG4gICAgICApXG5cbiAgICAgIHJldHVybiBzXG4gICAgfVxuXG4gICAgY29uc3Qgc3JjU2NlbmUgPSBta1NjZW5lKHNvdXJjZUZyYWcsIHNyY1UpXG4gICAgY29uc3QgbW9zaFNjZW5lID0gbWtTY2VuZShtb3NoRnJhZywgbW9zaFUpXG4gICAgY29uc3Qgb3V0U2NlbmUgPSBta1NjZW5lKG91dHB1dEZyYWcsIG91dFUsIHRydWUpXG5cbiAgICBjb25zdCByZXNpemUgPSAoKSA9PiB7XG4gICAgICByZW5kZXJlci5zZXRTaXplKGlubmVyV2lkdGgsIGlubmVySGVpZ2h0KVxuICAgICAgLy8gQ2FwIGF0IDEuNXggXHUyMDE0IEdyZXlzIGRvZXMgdHJpcGxlLWJ1ZmZlcmVkIHBpbmctcG9uZyByZW5kZXJpbmcgYXRcbiAgICAgIC8vIGV2ZXJ5IGZyYW1lLCBzbyByZXRpbmEgeDIgaXMgYnJ1dGFsIG9uIGZpbGxyYXRlLlxuICAgICAgcmVuZGVyZXIuc2V0UGl4ZWxSYXRpbyhNYXRoLm1pbihkZXZpY2VQaXhlbFJhdGlvLCAxLjUpKVxuICAgICAgO1tydFNvdXJjZSwgcnRBLCBydEJdLmZvckVhY2gocnQgPT4gcnQuc2V0U2l6ZShpbm5lcldpZHRoLCBpbm5lckhlaWdodCkpXG4gICAgICBtb3NoVS51UmVzLnZhbHVlLnNldChpbm5lcldpZHRoLCBpbm5lckhlaWdodClcbiAgICB9XG5cbiAgICByZXNpemUoKVxuICAgIHdpbmRvdy5hZGRFdmVudExpc3RlbmVyKCdyZXNpemUnLCByZXNpemUpXG5cbiAgICBsZXQgcGluZyA9IHRydWUsXG4gICAgICB0aW1lID0gMFxuXG4gICAgLy8gMzBmcHMgY2FwIFx1MjAxNCBmZWVkYmFjayBlZmZlY3QsIG5vIHBlcmNlcHR1YWwgbG9zcyB2cyA2MGZwcyBidXRcbiAgICAvLyBoYWx2ZXMgdGhlIGNvc3Qgb2YgdGhlIGhlYXZpZXN0IG92ZXJsYXkgd2Ugc2hpcC5cbiAgICBjb25zdCBkaXNwb3NlID0gcnVuUmVuZGVyTG9vcCh7XG4gICAgICBlbDogY2FudmFzUmVmLmN1cnJlbnQsXG4gICAgICBtaW5JbnRlcnZhbE1zOiAzMyxcbiAgICAgIG9uRnJhbWU6IGRlbHRhU2Vjb25kcyA9PiB7XG4gICAgICAgIHRpbWUgKz0gZGVsdGFTZWNvbmRzXG5cbiAgICAgICAgY29uc3QgdiA9IGNSZWYuY3VycmVudFxuXG4gICAgICAgIHNyY1UudVRpbWUudmFsdWUgPSB0aW1lXG4gICAgICAgIHNyY1UudVNwZWVkLnZhbHVlID0gdi5zcGVlZFxuICAgICAgICBzcmNVLnVab29tLnZhbHVlID0gdi56b29tXG4gICAgICAgIHNyY1UudVJvdGF0ZS52YWx1ZSA9IHYucm90YXRlXG4gICAgICAgIHNyY1UudUZvbGRzLnZhbHVlID0gdi5mb2xkc1xuICAgICAgICBzcmNVLnVEcmlmdC52YWx1ZSA9IHYuZHJpZnRcblxuICAgICAgICBtb3NoVS51VGltZS52YWx1ZSA9IHRpbWVcbiAgICAgICAgbW9zaFUudUludGVuc2l0eS52YWx1ZSA9IHYuaW50ZW5zaXR5XG4gICAgICAgIG1vc2hVLnVNb3Rpb24udmFsdWUgPSB2Lm1vdGlvblxuICAgICAgICBtb3NoVS51U3BlZWQudmFsdWUgPSB2LnNwZWVkXG4gICAgICAgIG1vc2hVLnVab29tLnZhbHVlID0gdi56b29tXG5cbiAgICAgICAgb3V0VS51VGltZS52YWx1ZSA9IHRpbWVcbiAgICAgICAgb3V0VS51QWxwaGEudmFsdWUgPSB2LmFscGhhXG4gICAgICAgIG91dFUudUh1ZS52YWx1ZSA9IHYuaHVlXG4gICAgICAgIG91dFUudUNvbG9yLnZhbHVlLnNldCh0eXBlb2Ygdi5jb2xvciA9PT0gJ3N0cmluZycgPyB2LmNvbG9yIDogJyNmZmYnKVxuXG4gICAgICAgIHJlbmRlcmVyLnNldFJlbmRlclRhcmdldChydFNvdXJjZSlcbiAgICAgICAgcmVuZGVyZXIucmVuZGVyKHNyY1NjZW5lLCBjYW1lcmEpXG5cbiAgICAgICAgY29uc3QgW3JlYWQsIHdyaXRlXSA9IHBpbmcgPyBbcnRBLCBydEJdIDogW3J0QiwgcnRBXVxuICAgICAgICBtb3NoVS51UHJldi52YWx1ZSA9IHJlYWQudGV4dHVyZVxuICAgICAgICByZW5kZXJlci5zZXRSZW5kZXJUYXJnZXQod3JpdGUpXG4gICAgICAgIHJlbmRlcmVyLnJlbmRlcihtb3NoU2NlbmUsIGNhbWVyYSlcblxuICAgICAgICBvdXRVLnVJbnB1dC52YWx1ZSA9IHdyaXRlLnRleHR1cmVcbiAgICAgICAgcmVuZGVyZXIuc2V0UmVuZGVyVGFyZ2V0KG51bGwpXG4gICAgICAgIHJlbmRlcmVyLnJlbmRlcihvdXRTY2VuZSwgY2FtZXJhKVxuXG4gICAgICAgIHBpbmcgPSAhcGluZ1xuICAgICAgfVxuICAgIH0pXG5cbiAgICByZXR1cm4gKCkgPT4ge1xuICAgICAgd2luZG93LnJlbW92ZUV2ZW50TGlzdGVuZXIoJ3Jlc2l6ZScsIHJlc2l6ZSlcbiAgICAgIGRpc3Bvc2UoKVxuICAgICAgdGV4dHVyZXMuZm9yRWFjaCh0ID0+IHQuZGlzcG9zZSgpKVxuICAgICAgO1tnZW8sIHJ0U291cmNlLCBydEEsIHJ0QiwgcmVuZGVyZXJdLmZvckVhY2goeCA9PiB4LmRpc3Bvc2UoKSlcbiAgICB9XG4gIH0sIFtlbmFibGVkXSlcblxuICBpZiAoIWVuYWJsZWQpIHtcbiAgICByZXR1cm4gbnVsbFxuICB9XG5cbiAgcmV0dXJuIChcbiAgICA8Y2FudmFzXG4gICAgICBjbGFzc05hbWU9e2NuKCdoLWZ1bGwgdy1mdWxsJywgY2xhc3NOYW1lKX1cbiAgICAgIHJlZj17Y2FudmFzUmVmfVxuICAgICAgc3R5bGU9e3tcbiAgICAgICAgbWl4QmxlbmRNb2RlOiAoYmxlbmRPdmVycmlkZSA/P1xuICAgICAgICAgIGMuYmxlbmQpIGFzIFJlYWN0LkNTU1Byb3BlcnRpZXNbJ21peEJsZW5kTW9kZSddLFxuICAgICAgICAuLi5zdHlsZVxuICAgICAgfX1cbiAgICAvPlxuICApXG59XG5cbmludGVyZmFjZSBHcmV5c1Byb3BzIHtcbiAgY2xhc3NOYW1lPzogc3RyaW5nXG4gIHN0eWxlPzogUmVhY3QuQ1NTUHJvcGVydGllc1xufSJdLAogICJtYXBwaW5ncyI6ICI7QUFrWEk7QUFoWEosU0FBUyxXQUFXLFFBQVEsZ0JBQWdCO0FBQzVDLFlBQVksV0FBVztBQUV2QixTQUFTLFVBQVUsa0JBQWtCO0FBQ3JDLFNBQVMscUJBQXFCO0FBQzlCLFNBQVMseUJBQXlCO0FBQ2xDLFNBQVMsVUFBVTtBQUVuQixTQUFTLG1CQUFtQjtBQUU1QixNQUFNO0FBQUE7QUFBQSxFQUFnQjtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBUXRCLE1BQU07QUFBQTtBQUFBLEVBQXNCO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQXVDNUIsTUFBTTtBQUFBO0FBQUEsRUFBb0I7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFB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
