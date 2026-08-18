"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import { useEffect, useRef } from "react";
const VERT = (
  /* glsl */
  `attribute vec2 a;void main(){gl_Position=vec4(a,0,1);}`
);
const FRAG = (
  /* glsl */
  `precision highp float;
uniform float t;
uniform vec2 r;

const float FBM_STR = .08;

float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float n2(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3. - 2. * f);

  return mix(
    mix(h(i), h(i + vec2(1, 0)), f.x),
    mix(h(i + vec2(0, 1)), h(i + vec2(1, 1)), f.x),
    f.y
  );
}

float fbm(vec2 p) {
  float v = 0., a = .5;

  for (int i = 0; i < 4; i++) {
    v += a * n2(p);
    p *= 2.1;
    a *= .45;
  }

  return v;
}

float drift(float speed, float s) {
  return fract(t * speed + s + .02 * sin(t * .4 + s * 3.));
}

float brushAt(vec2 uv, float y, float th, float s) {
  float hw = .34 + .08 * h(vec2(s, 77.));
  float cx = .5;
  float xn = (uv.x - (cx - hw)) / (2. * hw);
  float env = smoothstep(0., .03, xn) * smoothstep(1., .97, xn);
  float localTh = th * env;

  if (localTh < .002) return 0.;

  float morph = floor(t * 8.) * .7 + s;
  float top = y - localTh * .5 + fbm(vec2(uv.x * 6., morph)) * FBM_STR;
  float bot = y + localTh * .5 - fbm(vec2(uv.x * 6., morph + 30.)) * FBM_STR;
  float x0 = cx - hw + fbm(vec2(uv.y * 8., morph + 60.)) * FBM_STR;
  float x1 = cx + hw - fbm(vec2(uv.y * 8., morph + 90.)) * FBM_STR;

  float dMin = min(min(uv.y - top, bot - uv.y), min(uv.x - x0, x1 - uv.x));

  float bristle = n2(vec2(uv.x * 60., uv.y * 8. + s)) * .4
    + n2(vec2(uv.x * 25., (uv.y - y) * 120. + s)) * .35
    + n2(vec2(uv.x * 90., uv.y * 3. + s * 2.)) * .25;

  float eaten = smoothstep(.03, 0., dMin) * (1. - smoothstep(.2, .5, bristle));

  return clamp(smoothstep(0., .003, dMin) * (1. - eaten), 0., 1.);
}

void main() {
  vec2 uv = gl_FragCoord.xy / r;
  uv = vec2(uv.x * cos(.095) - uv.y * sin(.095), uv.x * sin(.095) + uv.y * cos(.095));
  uv += vec2(fbm(uv * 4. + t * .06), fbm(uv * 4. + 8. + t * .05)) * .012;

  vec3 c = vec3(.992, .992, .051);

  float smScroll = -drift(.04, 5.) * 2.;
  float sm = 0.;

  for (int i = 0; i < 20; i++) {
    sm = max(sm, brushAt(uv, mod(float(i) * .1 + smScroll, 2.) - .5, .04, float(i) + 10.));
  }

  float d1 = drift(.15, 1.), d2 = drift(.15, 1.37), d3 = drift(.15, 1.58), d4 = drift(.15, 1.82);
  float big = max(
    max(brushAt(uv, 1.1 - d1 * 1.4, .28, 1.), brushAt(uv, 1.1 - d2 * 1.4, .18, 2.)),
    max(brushAt(uv, 1.1 - d3 * 1.4, .3, 3.), brushAt(uv, 1.1 - d4 * 1.4, .15, 4.))
  );

  c = mix(c, vec3(0.), clamp(max(sm, big), 0., 1.));
  c *= .94 + .06 * sin(uv.y * r.y * 6.283);

  vec2 raw = gl_FragCoord.xy / r;
  float dx = min(raw.x - .22, .90 - raw.x);
  float dy = min(raw.y - .29, .86 - raw.y);
  float cycle = floor(t * .4);
  float edge = mix(smoothstep(.22, 0., max(min(dx, dy), 0.)), 1., step(.75, h(vec2(cycle, 13.))))
    * smoothstep(.85, 1., sin(t * 2.5) * .5 + .5)
    * (.7 + .3 * h(vec2(cycle, 7.)));

  float scanY = floor(gl_FragCoord.y);
  float rowNoise = h(vec2(scanY, floor(t * 30.)));
  c *= 1. - edge * max(step(.45, rowNoise), step(.3, h(vec2(gl_FragCoord.x + scanY * 7., floor(t * 45.)))) * step(.2, rowNoise));

  gl_FragColor = vec4(clamp(c, 0., 1.), 1.);
}`
);
function useGL(ref) {
  const raf = useRef(0);
  useEffect(() => {
    const c = ref.current;
    if (!c) {
      return;
    }
    const gl = c.getContext("webgl");
    if (!gl) {
      return;
    }
    const sh = (type, src) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      return s;
    };
    const p = gl.createProgram();
    gl.attachShader(p, sh(gl.VERTEX_SHADER, VERT));
    gl.attachShader(p, sh(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(p);
    gl.useProgram(p);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
      gl.STATIC_DRAW
    );
    const a = gl.getAttribLocation(p, "a");
    gl.enableVertexAttribArray(a);
    gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
    const uT = gl.getUniformLocation(p, "t");
    const uR = gl.getUniformLocation(p, "r");
    const resize = () => {
      const rect = c.getBoundingClientRect();
      const dpr = Math.min(devicePixelRatio, 2);
      c.width = rect.width * dpr;
      c.height = rect.height * dpr;
      gl.viewport(0, 0, c.width, c.height);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(c);
    const t0 = performance.now();
    let visible = !document.hidden;
    let inView = true;
    let raf2 = 0;
    const tick = () => {
      gl.uniform1f(uT, (performance.now() - t0) / 1e3);
      gl.uniform2f(uR, c.width, c.height);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      raf2 = requestAnimationFrame(tick);
    };
    const start = () => {
      if (visible && inView && !raf2) {
        raf2 = requestAnimationFrame(tick);
      }
    };
    const stop = () => {
      if (raf2) {
        cancelAnimationFrame(raf2);
        raf2 = 0;
      }
    };
    const onVisibility = () => {
      visible = !document.hidden;
      visible ? start() : stop();
    };
    const io = new IntersectionObserver(
      (entries) => {
        inView = entries.some((e) => e.isIntersecting);
        inView ? start() : stop();
      },
      { threshold: 0 }
    );
    io.observe(c);
    document.addEventListener("visibilitychange", onVisibility);
    start();
    raf.current = raf2;
    return () => {
      stop();
      io.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      ro.disconnect();
    };
  }, [ref]);
}
export function TV({ className }) {
  const canvasRef = useRef(null);
  useGL(canvasRef);
  return /* @__PURE__ */ jsxs("div", { className: ["relative", className].filter(Boolean).join(" "), children: [
    /* @__PURE__ */ jsxs("svg", { className: "relative h-full w-full", fill: "none", viewBox: "0 0 210 173", children: [
      /* @__PURE__ */ jsx(
        "path",
        {
          d: "M30.8342 2.44471 6.08268 36.683c-.24437.338-.38254.7412-.39689 1.158L1.57754 157.126c-.03891 1.129.82339 2.087 1.95096 2.167l162.4835 11.463c.433.031.866-.074 1.238-.3l35.718-21.69c.607-.369.986-1.02 1.008-1.73l4.102-130.9871c.035-1.1269-.826-2.0806-1.951-2.1604L32.6847 1.58029c-.7248-.05144-1.4247.27551-1.8505.86442Z",
          fill: "#FDFD0D",
          stroke: "#FDFD0D",
          strokeWidth: "3.15"
        }
      ),
      /* @__PURE__ */ jsx(
        "path",
        {
          d: "M203.09 17.1483 35.6844 5.83395l-4.2 121.94805 168.4906 13.076z",
          fill: "#000",
          stroke: "#FDFD0D",
          strokeWidth: "4.2"
        }
      ),
      /* @__PURE__ */ jsx(
        "path",
        {
          d: "M190.491 29.7483 48.2859 18.434l-4.2 98.848 143.2901 10.976z",
          fill: "#FDFD0D"
        }
      )
    ] }),
    /* @__PURE__ */ jsx(
      "canvas",
      {
        className: "absolute inset-0 h-full w-full",
        ref: canvasRef,
        style: {
          clipPath: "polygon(23% 10.65%, 90.71% 17.2%, 89.23% 74.13%, 20.99% 67.79%)"
        }
      }
    )
  ] });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZUVmZmVjdCwgdXNlUmVmIH0gZnJvbSAncmVhY3QnXG5cbmNvbnN0IFZFUlQgPSAvKiBnbHNsICovIGBhdHRyaWJ1dGUgdmVjMiBhO3ZvaWQgbWFpbigpe2dsX1Bvc2l0aW9uPXZlYzQoYSwwLDEpO31gXG5cbmNvbnN0IEZSQUcgPSAvKiBnbHNsICovIGBwcmVjaXNpb24gaGlnaHAgZmxvYXQ7XG51bmlmb3JtIGZsb2F0IHQ7XG51bmlmb3JtIHZlYzIgcjtcblxuY29uc3QgZmxvYXQgRkJNX1NUUiA9IC4wODtcblxuZmxvYXQgaCh2ZWMyIHApIHsgcmV0dXJuIGZyYWN0KHNpbihkb3QocCwgdmVjMigxMjcuMSwgMzExLjcpKSkgKiA0Mzc1OC41NDUzKTsgfVxuXG5mbG9hdCBuMih2ZWMyIHApIHtcbiAgdmVjMiBpID0gZmxvb3IocCksIGYgPSBmcmFjdChwKTtcbiAgZiA9IGYgKiBmICogKDMuIC0gMi4gKiBmKTtcblxuICByZXR1cm4gbWl4KFxuICAgIG1peChoKGkpLCBoKGkgKyB2ZWMyKDEsIDApKSwgZi54KSxcbiAgICBtaXgoaChpICsgdmVjMigwLCAxKSksIGgoaSArIHZlYzIoMSwgMSkpLCBmLngpLFxuICAgIGYueVxuICApO1xufVxuXG5mbG9hdCBmYm0odmVjMiBwKSB7XG4gIGZsb2F0IHYgPSAwLiwgYSA9IC41O1xuXG4gIGZvciAoaW50IGkgPSAwOyBpIDwgNDsgaSsrKSB7XG4gICAgdiArPSBhICogbjIocCk7XG4gICAgcCAqPSAyLjE7XG4gICAgYSAqPSAuNDU7XG4gIH1cblxuICByZXR1cm4gdjtcbn1cblxuZmxvYXQgZHJpZnQoZmxvYXQgc3BlZWQsIGZsb2F0IHMpIHtcbiAgcmV0dXJuIGZyYWN0KHQgKiBzcGVlZCArIHMgKyAuMDIgKiBzaW4odCAqIC40ICsgcyAqIDMuKSk7XG59XG5cbmZsb2F0IGJydXNoQXQodmVjMiB1diwgZmxvYXQgeSwgZmxvYXQgdGgsIGZsb2F0IHMpIHtcbiAgZmxvYXQgaHcgPSAuMzQgKyAuMDggKiBoKHZlYzIocywgNzcuKSk7XG4gIGZsb2F0IGN4ID0gLjU7XG4gIGZsb2F0IHhuID0gKHV2LnggLSAoY3ggLSBodykpIC8gKDIuICogaHcpO1xuICBmbG9hdCBlbnYgPSBzbW9vdGhzdGVwKDAuLCAuMDMsIHhuKSAqIHNtb290aHN0ZXAoMS4sIC45NywgeG4pO1xuICBmbG9hdCBsb2NhbFRoID0gdGggKiBlbnY7XG5cbiAgaWYgKGxvY2FsVGggPCAuMDAyKSByZXR1cm4gMC47XG5cbiAgZmxvYXQgbW9ycGggPSBmbG9vcih0ICogOC4pICogLjcgKyBzO1xuICBmbG9hdCB0b3AgPSB5IC0gbG9jYWxUaCAqIC41ICsgZmJtKHZlYzIodXYueCAqIDYuLCBtb3JwaCkpICogRkJNX1NUUjtcbiAgZmxvYXQgYm90ID0geSArIGxvY2FsVGggKiAuNSAtIGZibSh2ZWMyKHV2LnggKiA2LiwgbW9ycGggKyAzMC4pKSAqIEZCTV9TVFI7XG4gIGZsb2F0IHgwID0gY3ggLSBodyArIGZibSh2ZWMyKHV2LnkgKiA4LiwgbW9ycGggKyA2MC4pKSAqIEZCTV9TVFI7XG4gIGZsb2F0IHgxID0gY3ggKyBodyAtIGZibSh2ZWMyKHV2LnkgKiA4LiwgbW9ycGggKyA5MC4pKSAqIEZCTV9TVFI7XG5cbiAgZmxvYXQgZE1pbiA9IG1pbihtaW4odXYueSAtIHRvcCwgYm90IC0gdXYueSksIG1pbih1di54IC0geDAsIHgxIC0gdXYueCkpO1xuXG4gIGZsb2F0IGJyaXN0bGUgPSBuMih2ZWMyKHV2LnggKiA2MC4sIHV2LnkgKiA4LiArIHMpKSAqIC40XG4gICAgKyBuMih2ZWMyKHV2LnggKiAyNS4sICh1di55IC0geSkgKiAxMjAuICsgcykpICogLjM1XG4gICAgKyBuMih2ZWMyKHV2LnggKiA5MC4sIHV2LnkgKiAzLiArIHMgKiAyLikpICogLjI1O1xuXG4gIGZsb2F0IGVhdGVuID0gc21vb3Roc3RlcCguMDMsIDAuLCBkTWluKSAqICgxLiAtIHNtb290aHN0ZXAoLjIsIC41LCBicmlzdGxlKSk7XG5cbiAgcmV0dXJuIGNsYW1wKHNtb290aHN0ZXAoMC4sIC4wMDMsIGRNaW4pICogKDEuIC0gZWF0ZW4pLCAwLiwgMS4pO1xufVxuXG52b2lkIG1haW4oKSB7XG4gIHZlYzIgdXYgPSBnbF9GcmFnQ29vcmQueHkgLyByO1xuICB1diA9IHZlYzIodXYueCAqIGNvcyguMDk1KSAtIHV2LnkgKiBzaW4oLjA5NSksIHV2LnggKiBzaW4oLjA5NSkgKyB1di55ICogY29zKC4wOTUpKTtcbiAgdXYgKz0gdmVjMihmYm0odXYgKiA0LiArIHQgKiAuMDYpLCBmYm0odXYgKiA0LiArIDguICsgdCAqIC4wNSkpICogLjAxMjtcblxuICB2ZWMzIGMgPSB2ZWMzKC45OTIsIC45OTIsIC4wNTEpO1xuXG4gIGZsb2F0IHNtU2Nyb2xsID0gLWRyaWZ0KC4wNCwgNS4pICogMi47XG4gIGZsb2F0IHNtID0gMC47XG5cbiAgZm9yIChpbnQgaSA9IDA7IGkgPCAyMDsgaSsrKSB7XG4gICAgc20gPSBtYXgoc20sIGJydXNoQXQodXYsIG1vZChmbG9hdChpKSAqIC4xICsgc21TY3JvbGwsIDIuKSAtIC41LCAuMDQsIGZsb2F0KGkpICsgMTAuKSk7XG4gIH1cblxuICBmbG9hdCBkMSA9IGRyaWZ0KC4xNSwgMS4pLCBkMiA9IGRyaWZ0KC4xNSwgMS4zNyksIGQzID0gZHJpZnQoLjE1LCAxLjU4KSwgZDQgPSBkcmlmdCguMTUsIDEuODIpO1xuICBmbG9hdCBiaWcgPSBtYXgoXG4gICAgbWF4KGJydXNoQXQodXYsIDEuMSAtIGQxICogMS40LCAuMjgsIDEuKSwgYnJ1c2hBdCh1diwgMS4xIC0gZDIgKiAxLjQsIC4xOCwgMi4pKSxcbiAgICBtYXgoYnJ1c2hBdCh1diwgMS4xIC0gZDMgKiAxLjQsIC4zLCAzLiksIGJydXNoQXQodXYsIDEuMSAtIGQ0ICogMS40LCAuMTUsIDQuKSlcbiAgKTtcblxuICBjID0gbWl4KGMsIHZlYzMoMC4pLCBjbGFtcChtYXgoc20sIGJpZyksIDAuLCAxLikpO1xuICBjICo9IC45NCArIC4wNiAqIHNpbih1di55ICogci55ICogNi4yODMpO1xuXG4gIHZlYzIgcmF3ID0gZ2xfRnJhZ0Nvb3JkLnh5IC8gcjtcbiAgZmxvYXQgZHggPSBtaW4ocmF3LnggLSAuMjIsIC45MCAtIHJhdy54KTtcbiAgZmxvYXQgZHkgPSBtaW4ocmF3LnkgLSAuMjksIC44NiAtIHJhdy55KTtcbiAgZmxvYXQgY3ljbGUgPSBmbG9vcih0ICogLjQpO1xuICBmbG9hdCBlZGdlID0gbWl4KHNtb290aHN0ZXAoLjIyLCAwLiwgbWF4KG1pbihkeCwgZHkpLCAwLikpLCAxLiwgc3RlcCguNzUsIGgodmVjMihjeWNsZSwgMTMuKSkpKVxuICAgICogc21vb3Roc3RlcCguODUsIDEuLCBzaW4odCAqIDIuNSkgKiAuNSArIC41KVxuICAgICogKC43ICsgLjMgKiBoKHZlYzIoY3ljbGUsIDcuKSkpO1xuXG4gIGZsb2F0IHNjYW5ZID0gZmxvb3IoZ2xfRnJhZ0Nvb3JkLnkpO1xuICBmbG9hdCByb3dOb2lzZSA9IGgodmVjMihzY2FuWSwgZmxvb3IodCAqIDMwLikpKTtcbiAgYyAqPSAxLiAtIGVkZ2UgKiBtYXgoc3RlcCguNDUsIHJvd05vaXNlKSwgc3RlcCguMywgaCh2ZWMyKGdsX0ZyYWdDb29yZC54ICsgc2NhblkgKiA3LiwgZmxvb3IodCAqIDQ1LikpKSkgKiBzdGVwKC4yLCByb3dOb2lzZSkpO1xuXG4gIGdsX0ZyYWdDb2xvciA9IHZlYzQoY2xhbXAoYywgMC4sIDEuKSwgMS4pO1xufWBcblxuZnVuY3Rpb24gdXNlR0wocmVmOiBSZWFjdC5SZWZPYmplY3Q8SFRNTENhbnZhc0VsZW1lbnQgfCBudWxsPikge1xuICBjb25zdCByYWYgPSB1c2VSZWYoMClcblxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIGNvbnN0IGMgPSByZWYuY3VycmVudFxuXG4gICAgaWYgKCFjKSB7XG4gICAgICByZXR1cm5cbiAgICB9XG5cbiAgICBjb25zdCBnbCA9IGMuZ2V0Q29udGV4dCgnd2ViZ2wnKVxuXG4gICAgaWYgKCFnbCkge1xuICAgICAgcmV0dXJuXG4gICAgfVxuXG4gICAgY29uc3Qgc2ggPSAodHlwZTogbnVtYmVyLCBzcmM6IHN0cmluZykgPT4ge1xuICAgICAgY29uc3QgcyA9IGdsLmNyZWF0ZVNoYWRlcih0eXBlKSFcbiAgICAgIGdsLnNoYWRlclNvdXJjZShzLCBzcmMpXG4gICAgICBnbC5jb21waWxlU2hhZGVyKHMpXG5cbiAgICAgIHJldHVybiBzXG4gICAgfVxuXG4gICAgY29uc3QgcCA9IGdsLmNyZWF0ZVByb2dyYW0oKSFcbiAgICBnbC5hdHRhY2hTaGFkZXIocCwgc2goZ2wuVkVSVEVYX1NIQURFUiwgVkVSVCkpXG4gICAgZ2wuYXR0YWNoU2hhZGVyKHAsIHNoKGdsLkZSQUdNRU5UX1NIQURFUiwgRlJBRykpXG4gICAgZ2wubGlua1Byb2dyYW0ocClcbiAgICBnbC51c2VQcm9ncmFtKHApXG5cbiAgICBnbC5iaW5kQnVmZmVyKGdsLkFSUkFZX0JVRkZFUiwgZ2wuY3JlYXRlQnVmZmVyKCkpXG4gICAgZ2wuYnVmZmVyRGF0YShcbiAgICAgIGdsLkFSUkFZX0JVRkZFUixcbiAgICAgIG5ldyBGbG9hdDMyQXJyYXkoWy0xLCAtMSwgMSwgLTEsIC0xLCAxLCAxLCAxXSksXG4gICAgICBnbC5TVEFUSUNfRFJBV1xuICAgIClcblxuICAgIGNvbnN0IGEgPSBnbC5nZXRBdHRyaWJMb2NhdGlvbihwLCAnYScpXG4gICAgZ2wuZW5hYmxlVmVydGV4QXR0cmliQXJyYXkoYSlcbiAgICBnbC52ZXJ0ZXhBdHRyaWJQb2ludGVyKGEsIDIsIGdsLkZMT0FULCBmYWxzZSwgMCwgMClcblxuICAgIGNvbnN0IHVUID0gZ2wuZ2V0VW5pZm9ybUxvY2F0aW9uKHAsICd0JylcbiAgICBjb25zdCB1UiA9IGdsLmdldFVuaWZvcm1Mb2NhdGlvbihwLCAncicpXG5cbiAgICBjb25zdCByZXNpemUgPSAoKSA9PiB7XG4gICAgICBjb25zdCByZWN0ID0gYy5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKVxuICAgICAgY29uc3QgZHByID0gTWF0aC5taW4oZGV2aWNlUGl4ZWxSYXRpbywgMilcblxuICAgICAgYy53aWR0aCA9IHJlY3Qud2lkdGggKiBkcHJcbiAgICAgIGMuaGVpZ2h0ID0gcmVjdC5oZWlnaHQgKiBkcHJcblxuICAgICAgZ2wudmlld3BvcnQoMCwgMCwgYy53aWR0aCwgYy5oZWlnaHQpXG4gICAgfVxuXG4gICAgcmVzaXplKClcblxuICAgIGNvbnN0IHJvID0gbmV3IFJlc2l6ZU9ic2VydmVyKHJlc2l6ZSlcbiAgICByby5vYnNlcnZlKGMpXG5cbiAgICBjb25zdCB0MCA9IHBlcmZvcm1hbmNlLm5vdygpXG5cbiAgICBsZXQgdmlzaWJsZSA9ICFkb2N1bWVudC5oaWRkZW5cbiAgICBsZXQgaW5WaWV3ID0gdHJ1ZVxuICAgIGxldCByYWYyID0gMFxuXG4gICAgY29uc3QgdGljayA9ICgpID0+IHtcbiAgICAgIGdsLnVuaWZvcm0xZih1VCwgKHBlcmZvcm1hbmNlLm5vdygpIC0gdDApIC8gMWUzKVxuICAgICAgZ2wudW5pZm9ybTJmKHVSLCBjLndpZHRoLCBjLmhlaWdodClcbiAgICAgIGdsLmRyYXdBcnJheXMoZ2wuVFJJQU5HTEVfU1RSSVAsIDAsIDQpXG5cbiAgICAgIHJhZjIgPSByZXF1ZXN0QW5pbWF0aW9uRnJhbWUodGljaylcbiAgICB9XG5cbiAgICBjb25zdCBzdGFydCA9ICgpID0+IHtcbiAgICAgIGlmICh2aXNpYmxlICYmIGluVmlldyAmJiAhcmFmMikge1xuICAgICAgICByYWYyID0gcmVxdWVzdEFuaW1hdGlvbkZyYW1lKHRpY2spXG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3Qgc3RvcCA9ICgpID0+IHtcbiAgICAgIGlmIChyYWYyKSB7XG4gICAgICAgIGNhbmNlbEFuaW1hdGlvbkZyYW1lKHJhZjIpXG4gICAgICAgIHJhZjIgPSAwXG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3Qgb25WaXNpYmlsaXR5ID0gKCkgPT4ge1xuICAgICAgdmlzaWJsZSA9ICFkb2N1bWVudC5oaWRkZW5cbiAgICAgIHZpc2libGUgPyBzdGFydCgpIDogc3RvcCgpXG4gICAgfVxuXG4gICAgY29uc3QgaW8gPSBuZXcgSW50ZXJzZWN0aW9uT2JzZXJ2ZXIoXG4gICAgICBlbnRyaWVzID0+IHtcbiAgICAgICAgaW5WaWV3ID0gZW50cmllcy5zb21lKGUgPT4gZS5pc0ludGVyc2VjdGluZylcbiAgICAgICAgaW5WaWV3ID8gc3RhcnQoKSA6IHN0b3AoKVxuICAgICAgfSxcbiAgICAgIHsgdGhyZXNob2xkOiAwIH1cbiAgICApXG5cbiAgICBpby5vYnNlcnZlKGMpXG4gICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcigndmlzaWJpbGl0eWNoYW5nZScsIG9uVmlzaWJpbGl0eSlcblxuICAgIHN0YXJ0KClcbiAgICByYWYuY3VycmVudCA9IHJhZjJcblxuICAgIHJldHVybiAoKSA9PiB7XG4gICAgICBzdG9wKClcbiAgICAgIGlvLmRpc2Nvbm5lY3QoKVxuICAgICAgZG9jdW1lbnQucmVtb3ZlRXZlbnRMaXN0ZW5lcigndmlzaWJpbGl0eWNoYW5nZScsIG9uVmlzaWJpbGl0eSlcbiAgICAgIHJvLmRpc2Nvbm5lY3QoKVxuICAgIH1cbiAgfSwgW3JlZl0pXG59XG5cbmV4cG9ydCBmdW5jdGlvbiBUVih7IGNsYXNzTmFtZSB9OiB7IGNsYXNzTmFtZT86IHN0cmluZyB9KSB7XG4gIGNvbnN0IGNhbnZhc1JlZiA9IHVzZVJlZjxIVE1MQ2FudmFzRWxlbWVudD4obnVsbClcbiAgdXNlR0woY2FudmFzUmVmKVxuXG4gIHJldHVybiAoXG4gICAgPGRpdiBjbGFzc05hbWU9e1sncmVsYXRpdmUnLCBjbGFzc05hbWVdLmZpbHRlcihCb29sZWFuKS5qb2luKCcgJyl9PlxuICAgICAgPHN2ZyBjbGFzc05hbWU9XCJyZWxhdGl2ZSBoLWZ1bGwgdy1mdWxsXCIgZmlsbD1cIm5vbmVcIiB2aWV3Qm94PVwiMCAwIDIxMCAxNzNcIj5cbiAgICAgICAgPHBhdGhcbiAgICAgICAgICBkPVwiTTMwLjgzNDIgMi40NDQ3MSA2LjA4MjY4IDM2LjY4M2MtLjI0NDM3LjMzOC0uMzgyNTQuNzQxMi0uMzk2ODkgMS4xNThMMS41Nzc1NCAxNTcuMTI2Yy0uMDM4OTEgMS4xMjkuODIzMzkgMi4wODcgMS45NTA5NiAyLjE2N2wxNjIuNDgzNSAxMS40NjNjLjQzMy4wMzEuODY2LS4wNzQgMS4yMzgtLjNsMzUuNzE4LTIxLjY5Yy42MDctLjM2OS45ODYtMS4wMiAxLjAwOC0xLjczbDQuMTAyLTEzMC45ODcxYy4wMzUtMS4xMjY5LS44MjYtMi4wODA2LTEuOTUxLTIuMTYwNEwzMi42ODQ3IDEuNTgwMjljLS43MjQ4LS4wNTE0NC0xLjQyNDcuMjc1NTEtMS44NTA1Ljg2NDQyWlwiXG4gICAgICAgICAgZmlsbD1cIiNGREZEMERcIlxuICAgICAgICAgIHN0cm9rZT1cIiNGREZEMERcIlxuICAgICAgICAgIHN0cm9rZVdpZHRoPVwiMy4xNVwiXG4gICAgICAgIC8+XG5cbiAgICAgICAgPHBhdGhcbiAgICAgICAgICBkPVwiTTIwMy4wOSAxNy4xNDgzIDM1LjY4NDQgNS44MzM5NWwtNC4yIDEyMS45NDgwNSAxNjguNDkwNiAxMy4wNzZ6XCJcbiAgICAgICAgICBmaWxsPVwiIzAwMFwiXG4gICAgICAgICAgc3Ryb2tlPVwiI0ZERkQwRFwiXG4gICAgICAgICAgc3Ryb2tlV2lkdGg9XCI0LjJcIlxuICAgICAgICAvPlxuXG4gICAgICAgIDxwYXRoXG4gICAgICAgICAgZD1cIk0xOTAuNDkxIDI5Ljc0ODMgNDguMjg1OSAxOC40MzRsLTQuMiA5OC44NDggMTQzLjI5MDEgMTAuOTc2elwiXG4gICAgICAgICAgZmlsbD1cIiNGREZEMERcIlxuICAgICAgICAvPlxuICAgICAgPC9zdmc+XG5cbiAgICAgIDxjYW52YXNcbiAgICAgICAgY2xhc3NOYW1lPVwiYWJzb2x1dGUgaW5zZXQtMCBoLWZ1bGwgdy1mdWxsXCJcbiAgICAgICAgcmVmPXtjYW52YXNSZWZ9XG4gICAgICAgIHN0eWxlPXt7XG4gICAgICAgICAgY2xpcFBhdGg6XG4gICAgICAgICAgICAncG9seWdvbigyMyUgMTAuNjUlLCA5MC43MSUgMTcuMiUsIDg5LjIzJSA3NC4xMyUsIDIwLjk5JSA2Ny43OSUpJ1xuICAgICAgICB9fVxuICAgICAgLz5cbiAgICA8L2Rpdj5cbiAgKVxufVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQWlPTSxTQUNFLEtBREY7QUEvTk4sU0FBUyxXQUFXLGNBQWM7QUFFbEMsTUFBTTtBQUFBO0FBQUEsRUFBa0I7QUFBQTtBQUV4QixNQUFNO0FBQUE7QUFBQSxFQUFrQjtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFtR3hCLFNBQVMsTUFBTSxLQUFnRDtBQUM3RCxRQUFNLE1BQU0sT0FBTyxDQUFDO0FBRXBCLFlBQVUsTUFBTTtBQUNkLFVBQU0sSUFBSSxJQUFJO0FBRWQsUUFBSSxDQUFDLEdBQUc7QUFDTjtBQUFBLElBQ0Y7QUFFQSxVQUFNLEtBQUssRUFBRSxXQUFXLE9BQU87QUFFL0IsUUFBSSxDQUFDLElBQUk7QUFDUDtB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
