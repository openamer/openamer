"use client";
import { jsx } from "react/jsx-runtime";
import { useEffect, useRef, useState } from "react";
import { useGpuTier } from "../../hooks/use-gpu-tier.js";
import { cn, hexToRgb } from "../../utils/index.js";
const NUM_BANDS = 12;
const VERT = `attribute vec2 a;varying vec2 vUv;void main(){vUv=vec2(a.x*.5+.5,.5-a.y*.5);gl_Position=vec4(a,0,1);}`;
const FRAG = `precision highp float;
uniform float t;
uniform vec2 r,imgSize,vel;
uniform sampler2D tex;
uniform float bands[${NUM_BANDS}];
uniform vec3 tint;
uniform float tintStrength;
varying vec2 vUv;

float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}

// cover-style UV: crops the image to fill the canvas, centered
vec2 coverUV(vec2 uv){
  float canvasAspect=r.x/r.y;
  float imgAspect=imgSize.x/imgSize.y;
  vec2 scale=canvasAspect>imgAspect
    ?vec2(1.0,imgAspect/canvasAspect)
    :vec2(canvasAspect/imgAspect,1.0);
  return(uv-0.5)*scale+0.5;
}

void main(){
  vec2 uv=coverUV(vUv);
  float scanY=floor(vUv.y*r.y);

  float bandF=vUv.y*${NUM_BANDS}.0;
  int bandIdx=int(floor(bandF));
  float bandFrac=fract(bandF);

  float strength=0.0;
  for(int i=0;i<${NUM_BANDS};i++){
    if(i==bandIdx) strength=bands[i];
  }

  float neighborStr=0.0;
  int neighborIdx=bandFrac>.5?bandIdx+1:bandIdx-1;
  for(int i=0;i<${NUM_BANDS};i++){
    if(i==neighborIdx) neighborStr=bands[i];
  }
  float edgeBlend=abs(bandFrac-.5)*2.0;
  edgeBlend*=edgeBlend;
  strength=mix(strength,neighborStr,edgeBlend*.3);

  float speed=length(vel);
  float dirBlend=smoothstep(0.0,0.02,speed);
  vec2 dir=speed>.0001?vel/speed:vec2(0);
  dir*=dirBlend;

  float rowSeed=h(vec2(scanY,floor(t*3.)+float(bandIdx)*7.));
  float rowVar=mix(.4,1.0,rowSeed);

  float ySmooth=vUv.y*6.0+t*0.7;
  float yNoise=mix(h(vec2(floor(ySmooth),13.)),h(vec2(floor(ySmooth)+1.0,13.)),smoothstep(0.0,1.0,fract(ySmooth)));
  float colVar=mix(.4,1.0,yNoise);

  float tearShiftX=dir.x*strength*rowVar*0.15;
  float tearShiftY=dir.y*strength*colVar*0.10;

  float bandSeed=h(vec2(float(bandIdx),42.));
  tearShiftX+=strength*(.5-bandSeed)*0.05;

  float yJitter=mix(h(vec2(floor(ySmooth),73.)),h(vec2(floor(ySmooth)+1.0,73.)),smoothstep(0.0,1.0,fract(ySmooth)));
  tearShiftY+=strength*(.5-yJitter)*0.035;

  uv.x+=tearShiftX;
  uv.y+=tearShiftY;

  float sortGate=step(.5,strength)*step(.4,rowSeed);
  uv.x+=dir.x*sortGate*strength*0.03;
  uv.y+=dir.y*sortGate*strength*0.02;

  float caX=abs(tearShiftX)*2.5+sortGate*strength*0.01;
  float caY=abs(tearShiftY)*2.5+sortGate*strength*0.01;
  float cr=texture2D(tex,vec2(uv.x+caX,uv.y+caY)).r;
  float cg=texture2D(tex,uv).g;
  float cb=texture2D(tex,vec2(uv.x-caX,uv.y-caY)).b;

  vec3 col=vec3(cr,cg,cb);

  col*=.97+.03*sin(vUv.y*r.y*3.14159);

  float bandEdge=smoothstep(.02,.0,min(bandFrac,1.0-bandFrac));
  col+=vec3(bandEdge*strength*.1);

  col=mix(col,col*tint,tintStrength);

  gl_FragColor=vec4(col,1.0);
}`;
const AUTOPLAY_PATTERNS = {
  aggressive: (t) => {
    const cycle = 1.4;
    const phase = t % cycle / cycle;
    const stab = Math.exp(-((phase - 0.15) ** 2) * 260);
    const angle = Math.floor(t / cycle) * 1.37;
    const mx = 0.5 + Math.cos(angle) * 0.42 * (stab + 0.15);
    const my = 0.5 + Math.sin(angle) * 0.38 * (stab + 0.15);
    return { hover: 0.55 + stab * 0.45, mx, my };
  },
  gentle: (t) => ({
    hover: 0.45 + Math.sin(t * 0.9) * 0.1,
    mx: 0.5 + Math.sin(t * 0.5) * 0.28,
    my: 0.5 + Math.cos(t * 0.37) * 0.22
  }),
  slash: (t) => {
    const cycle = 3.6;
    const phase = t % cycle / cycle;
    const slash = Math.exp(-((phase - 0.28) ** 2) * 180);
    const micro = Math.exp(-((phase - 0.7) ** 2) * 340);
    const driftX = 0.5 + Math.sin(t * 0.7) * 0.16;
    const driftY = 0.55 + Math.cos(t * 0.5) * 0.14;
    const slashX = -0.15 + phase * 1.55;
    const slashY = 0.95 - phase * 1.35;
    const mx = driftX * (1 - slash) + slashX * slash;
    const my = driftY * (1 - slash) + slashY * slash;
    return { hover: 0.5 + slash * 0.5 + micro * 0.35, mx, my };
  }
};
export function ImageDistortion({
  active = true,
  autoPlay,
  className,
  fallbackClassName,
  src,
  style,
  tint,
  tintStrength
}) {
  const canvasRef = useRef(null);
  const tier = useGpuTier();
  const [loaded, setLoaded] = useState(false);
  const activeRef = useRef(active);
  activeRef.current = active;
  const tintStrengthRef = useRef(tintStrength);
  tintStrengthRef.current = tintStrength;
  const autoPlayRef = useRef(autoPlay);
  autoPlayRef.current = autoPlay;
  const state = useRef({
    bandTargets: new Float32Array(NUM_BANDS),
    bands: new Float32Array(NUM_BANDS),
    hoverTarget: 0,
    imgH: 1,
    imgW: 1,
    mx: 0.5,
    my: 0.5,
    prevMx: 0.5,
    prevMy: 0.5,
    vx: 0,
    vy: 0
  });
  useEffect(() => {
    if (tier === 0) {
      return;
    }
    const c = canvasRef.current;
    if (!c) {
      return;
    }
    const gl = c.getContext("webgl");
    if (!gl) {
      return;
    }
    const compile = (type, source) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, source);
      gl.compileShader(s);
      return s;
    };
    const prog = gl.createProgram();
    gl.attachShader(prog, compile(gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    gl.useProgram(prog);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
      gl.STATIC_DRAW
    );
    const a = gl.getAttribLocation(prog, "a");
    gl.enableVertexAttribArray(a);
    gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
    const uT = gl.getUniformLocation(prog, "t");
    const uR = gl.getUniformLocation(prog, "r");
    const uImgSize = gl.getUniformLocation(prog, "imgSize");
    const uVel = gl.getUniformLocation(prog, "vel");
    const uTex = gl.getUniformLocation(prog, "tex");
    const uTint = gl.getUniformLocation(prog, "tint");
    const uTintStrength = gl.getUniformLocation(prog, "tintStrength");
    const uBands = [];
    for (let i = 0; i < NUM_BANDS; i++) {
      uBands.push(gl.getUniformLocation(prog, `bands[${i}]`));
    }
    const texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      gl.RGBA,
      1,
      1,
      0,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      new Uint8Array([0, 0, 0, 255])
    );
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      state.current.imgW = img.naturalWidth;
      state.current.imgH = img.naturalHeight;
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.RGBA,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        img
      );
      setLoaded(true);
    };
    img.src = src;
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.uniform1i(uTex, 0);
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
    const onMove = (e) => {
      const rect = c.getBoundingClientRect();
      state.current.mx = (e.clientX - rect.left) / rect.width;
      state.current.my = (e.clientY - rect.top) / rect.height;
    };
    const onEnter = () => {
      state.current.hoverTarget = 1;
    };
    const onLeave = () => {
      state.current.hoverTarget = 0;
    };
    if (!autoPlayRef.current) {
      c.addEventListener("pointermove", onMove);
      c.addEventListener("pointerenter", onEnter);
      c.addEventListener("pointerleave", onLeave);
    }
    const bandEaseRates = new Float32Array(NUM_BANDS);
    for (let i = 0; i < NUM_BANDS; i++) {
      bandEaseRates[i] = 0.02 + Math.random() * 0.06;
    }
    const tintVec = tint ? (() => {
      const [tr, tg, tb] = hexToRgb(tint);
      return [tr / 255, tg / 255, tb / 255];
    })() : [1, 1, 1];
    const t0 = performance.now();
    let raf = 0;
    let visible = !document.hidden;
    let inView = true;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      const s = state.current;
      const pattern = autoPlayRef.current ? AUTOPLAY_PATTERNS[autoPlayRef.current] : null;
      if (pattern) {
        const driven = pattern((performance.now() - t0) / 1e3);
        s.mx = driven.mx;
        s.my = driven.my;
        s.hoverTarget = driven.hover;
      }
      const dvx = s.mx - s.prevMx;
      const dvy = s.my - s.prevMy;
      s.vx += (dvx * 8 - s.vx) * 0.1;
      s.vy += (dvy * 8 - s.vy) * 0.1;
      s.prevMx = s.mx;
      s.prevMy = s.my;
      const speed = Math.sqrt(s.vx * s.vx + s.vy * s.vy);
      for (let i = 0; i < NUM_BANDS; i++) {
        const bandCenter = (i + 0.5) / NUM_BANDS;
        const dist = Math.abs(s.my - bandCenter);
        const proximity = Math.max(0, 1 - dist / 0.3);
        const activation = s.hoverTarget * proximity * (0.4 + Math.min(speed, 1) * 0.6);
        s.bandTargets[i] = activation;
      }
      for (let i = 0; i < NUM_BANDS; i++) {
        const rate = bandEaseRates[i];
        const current = s.bands[i] ?? 0;
        const target = s.bandTargets[i] ?? 0;
        s.bands[i] = current + (target - current) * rate;
        if (s.bands[i] < 1e-3) {
          s.bands[i] = 0;
        }
      }
      gl.uniform1f(uT, (performance.now() - t0) / 1e3);
      gl.uniform2f(uR, c.width, c.height);
      gl.uniform2f(uImgSize, s.imgW, s.imgH);
      gl.uniform2f(uVel, s.vx, s.vy);
      gl.uniform3f(uTint, tintVec[0], tintVec[1], tintVec[2]);
      const ts = tintStrengthRef.current;
      const defaultStrength = tint ? 0.35 : 0;
      const defaultInactive = tint ? 0.15 : 0;
      gl.uniform1f(
        uTintStrength,
        activeRef.current ? ts?.active ?? defaultStrength : ts?.inactive ?? defaultInactive
      );
      for (let i = 0; i < NUM_BANDS; i++) {
        gl.uniform1f(uBands[i], s.bands[i]);
      }
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    };
    const start = () => {
      if (visible && inView && !raf) {
        raf = requestAnimationFrame(loop);
      }
    };
    const stop = () => {
      if (raf) {
        cancelAnimationFrame(raf);
        raf = 0;
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
    return () => {
      stop();
      io.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      ro.disconnect();
      c.removeEventListener("pointermove", onMove);
      c.removeEventListener("pointerenter", onEnter);
      c.removeEventListener("pointerleave", onLeave);
      gl.deleteTexture(texture);
      gl.deleteProgram(prog);
      setLoaded(false);
    };
  }, [src, tier, tint]);
  if (tier === 0) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      /* @__PURE__ */ jsx(
        "img",
        {
          alt: "",
          className: cn(
            "absolute inset-0 h-full w-full object-cover",
            fallbackClassName ?? className
          ),
          fetchPriority: "high",
          src,
          style: { mixBlendMode: "overlay", ...style }
        }
      )
    );
  }
  return /* @__PURE__ */ jsx(
    "canvas",
    {
      className: cn(
        "absolute inset-0 h-full w-full transition-opacity duration-500",
        className
      ),
      ref: canvasRef,
      style: {
        mixBlendMode: "overlay",
        opacity: loaded ? 1 : 0,
        ...style
      }
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZUVmZmVjdCwgdXNlUmVmLCB1c2VTdGF0ZSB9IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyB1c2VHcHVUaWVyIH0gZnJvbSAnLi4vLi4vaG9va3MvdXNlLWdwdS10aWVyJ1xuaW1wb3J0IHsgY24sIGhleFRvUmdiIH0gZnJvbSAnLi4vLi4vdXRpbHMnXG5cbmNvbnN0IE5VTV9CQU5EUyA9IDEyXG5cbmNvbnN0IFZFUlQgPSBgYXR0cmlidXRlIHZlYzIgYTt2YXJ5aW5nIHZlYzIgdlV2O3ZvaWQgbWFpbigpe3ZVdj12ZWMyKGEueCouNSsuNSwuNS1hLnkqLjUpO2dsX1Bvc2l0aW9uPXZlYzQoYSwwLDEpO31gXG5cbmNvbnN0IEZSQUcgPSBgcHJlY2lzaW9uIGhpZ2hwIGZsb2F0O1xudW5pZm9ybSBmbG9hdCB0O1xudW5pZm9ybSB2ZWMyIHIsaW1nU2l6ZSx2ZWw7XG51bmlmb3JtIHNhbXBsZXIyRCB0ZXg7XG51bmlmb3JtIGZsb2F0IGJhbmRzWyR7TlVNX0JBTkRTfV07XG51bmlmb3JtIHZlYzMgdGludDtcbnVuaWZvcm0gZmxvYXQgdGludFN0cmVuZ3RoO1xudmFyeWluZyB2ZWMyIHZVdjtcblxuZmxvYXQgaCh2ZWMyIHApe3JldHVybiBmcmFjdChzaW4oZG90KHAsdmVjMigxMjcuMSwzMTEuNykpKSo0Mzc1OC41NDUzKTt9XG5cbi8vIGNvdmVyLXN0eWxlIFVWOiBjcm9wcyB0aGUgaW1hZ2UgdG8gZmlsbCB0aGUgY2FudmFzLCBjZW50ZXJlZFxudmVjMiBjb3ZlclVWKHZlYzIgdXYpe1xuICBmbG9hdCBjYW52YXNBc3BlY3Q9ci54L3IueTtcbiAgZmxvYXQgaW1nQXNwZWN0PWltZ1NpemUueC9pbWdTaXplLnk7XG4gIHZlYzIgc2NhbGU9Y2FudmFzQXNwZWN0PmltZ0FzcGVjdFxuICAgID92ZWMyKDEuMCxpbWdBc3BlY3QvY2FudmFzQXNwZWN0KVxuICAgIDp2ZWMyKGNhbnZhc0FzcGVjdC9pbWdBc3BlY3QsMS4wKTtcbiAgcmV0dXJuKHV2LTAuNSkqc2NhbGUrMC41O1xufVxuXG52b2lkIG1haW4oKXtcbiAgdmVjMiB1dj1jb3ZlclVWKHZVdik7XG4gIGZsb2F0IHNjYW5ZPWZsb29yKHZVdi55KnIueSk7XG5cbiAgZmxvYXQgYmFuZEY9dlV2LnkqJHtOVU1fQkFORFN9LjA7XG4gIGludCBiYW5kSWR4PWludChmbG9vcihiYW5kRikpO1xuICBmbG9hdCBiYW5kRnJhYz1mcmFjdChiYW5kRik7XG5cbiAgZmxvYXQgc3RyZW5ndGg9MC4wO1xuICBmb3IoaW50IGk9MDtpPCR7TlVNX0JBTkRTfTtpKyspe1xuICAgIGlmKGk9PWJhbmRJZHgpIHN0cmVuZ3RoPWJhbmRzW2ldO1xuICB9XG5cbiAgZmxvYXQgbmVpZ2hib3JTdHI9MC4wO1xuICBpbnQgbmVpZ2hib3JJZHg9YmFuZEZyYWM+LjU/YmFuZElkeCsxOmJhbmRJZHgtMTtcbiAgZm9yKGludCBpPTA7aTwke05VTV9CQU5EU307aSsrKXtcbiAgICBpZihpPT1uZWlnaGJvcklkeCkgbmVpZ2hib3JTdHI9YmFuZHNbaV07XG4gIH1cbiAgZmxvYXQgZWRnZUJsZW5kPWFicyhiYW5kRnJhYy0uNSkqMi4wO1xuICBlZGdlQmxlbmQqPWVkZ2VCbGVuZDtcbiAgc3RyZW5ndGg9bWl4KHN0cmVuZ3RoLG5laWdoYm9yU3RyLGVkZ2VCbGVuZCouMyk7XG5cbiAgZmxvYXQgc3BlZWQ9bGVuZ3RoKHZlbCk7XG4gIGZsb2F0IGRpckJsZW5kPXNtb290aHN0ZXAoMC4wLDAuMDIsc3BlZWQpO1xuICB2ZWMyIGRpcj1zcGVlZD4uMDAwMT92ZWwvc3BlZWQ6dmVjMigwKTtcbiAgZGlyKj1kaXJCbGVuZDtcblxuICBmbG9hdCByb3dTZWVkPWgodmVjMihzY2FuWSxmbG9vcih0KjMuKStmbG9hdChiYW5kSWR4KSo3LikpO1xuICBmbG9hdCByb3dWYXI9bWl4KC40LDEuMCxyb3dTZWVkKTtcblxuICBmbG9hdCB5U21vb3RoPXZVdi55KjYuMCt0KjAuNztcbiAgZmxvYXQgeU5vaXNlPW1peChoKHZlYzIoZmxvb3IoeVNtb290aCksMTMuKSksaCh2ZWMyKGZsb29yKHlTbW9vdGgpKzEuMCwxMy4pKSxzbW9vdGhzdGVwKDAuMCwxLjAsZnJhY3QoeVNtb290aCkpKTtcbiAgZmxvYXQgY29sVmFyPW1peCguNCwxLjAseU5vaXNlKTtcblxuICBmbG9hdCB0ZWFyU2hpZnRYPWRpci54KnN0cmVuZ3RoKnJvd1ZhciowLjE1O1xuICBmbG9hdCB0ZWFyU2hpZnRZPWRpci55KnN0cmVuZ3RoKmNvbFZhciowLjEwO1xuXG4gIGZsb2F0IGJhbmRTZWVkPWgodmVjMihmbG9hdChiYW5kSWR4KSw0Mi4pKTtcbiAgdGVhclNoaWZ0WCs9c3RyZW5ndGgqKC41LWJhbmRTZWVkKSowLjA1O1xuXG4gIGZsb2F0IHlKaXR0ZXI9bWl4KGgodmVjMihmbG9vcih5U21vb3RoKSw3My4pKSxoKHZlYzIoZmxvb3IoeVNtb290aCkrMS4wLDczLikpLHNtb290aHN0ZXAoMC4wLDEuMCxmcmFjdCh5U21vb3RoKSkpO1xuICB0ZWFyU2hpZnRZKz1zdHJlbmd0aCooLjUteUppdHRlcikqMC4wMzU7XG5cbiAgdXYueCs9dGVhclNoaWZ0WDtcbiAgdXYueSs9dGVhclNoaWZ0WTtcblxuICBmbG9hdCBzb3J0R2F0ZT1zdGVwKC41LHN0cmVuZ3RoKSpzdGVwKC40LHJvd1NlZWQpO1xuICB1di54Kz1kaXIueCpzb3J0R2F0ZSpzdHJlbmd0aCowLjAzO1xuICB1di55Kz1kaXIueSpzb3J0R2F0ZSpzdHJlbmd0aCowLjAyO1xuXG4gIGZsb2F0IGNhWD1hYnModGVhclNoaWZ0WCkqMi41K3NvcnRHYXRlKnN0cmVuZ3RoKjAuMDE7XG4gIGZsb2F0IGNhWT1hYnModGVhclNoaWZ0WSkqMi41K3NvcnRHYXRlKnN0cmVuZ3RoKjAuMDE7XG4gIGZsb2F0IGNyPXRleHR1cmUyRCh0ZXgsdmVjMih1di54K2NhWCx1di55K2NhWSkpLnI7XG4gIGZsb2F0IGNnPXRleHR1cmUyRCh0ZXgsdXYpLmc7XG4gIGZsb2F0IGNiPXRleHR1cmUyRCh0ZXgsdmVjMih1di54LWNhWCx1di55LWNhWSkpLmI7XG5cbiAgdmVjMyBjb2w9dmVjMyhjcixjZyxjYik7XG5cbiAgY29sKj0uOTcrLjAzKnNpbih2VXYueSpyLnkqMy4xNDE1OSk7XG5cbiAgZmxvYXQgYmFuZEVkZ2U9c21vb3Roc3RlcCguMDIsLjAsbWluKGJhbmRGcmFjLDEuMC1iYW5kRnJhYykpO1xuICBjb2wrPXZlYzMoYmFuZEVkZ2Uqc3RyZW5ndGgqLjEpO1xuXG4gIGNvbD1taXgoY29sLGNvbCp0aW50LHRpbnRTdHJlbmd0aCk7XG5cbiAgZ2xfRnJhZ0NvbG9yPXZlYzQoY29sLDEuMCk7XG59YFxuXG4vKipcbiAqIENob3Jlb2dyYXBoZWQgbW90aW9uIHBhdHRlcm5zIHVzZWQgd2hlbiBgYXV0b1BsYXlgIGlzIHNldC4gRWFjaCBwYXR0ZXJuXG4gKiByZXR1cm5zIGEgc3ludGhldGljIHBvaW50ZXIgcG9zaXRpb24gaW4gWzAsMV0gYW5kIGEgaG92ZXIgaW50ZW5zaXR5IGluXG4gKiBbMCwxXSBmb3IgdGhlIGN1cnJlbnQgdGltZSAoc2Vjb25kcykuIFRoZXkgZHJpdmUgdGhlIHNoYWRlciB3aXRob3V0XG4gKiByZXF1aXJpbmcgYSByZWFsIHBvaW50ZXIsIHdoaWNoIGlzIHdoYXQgbGV0cyB1cyByZWNvcmQgdGhlIGRpc3RvcnRpb25cbiAqIGFzIGEgR0lGIC8gc2NyZWVuc2hvdCAvIHBvc3Rlci5cbiAqL1xuY29uc3QgQVVUT1BMQVlfUEFUVEVSTlM6IFJlY29yZDxcbiAgQXV0b1BsYXlQYXR0ZXJuLFxuICAodDogbnVtYmVyKSA9PiB7IGhvdmVyOiBudW1iZXI7IG14OiBudW1iZXI7IG15OiBudW1iZXIgfVxuPiA9IHtcbiAgYWdncmVzc2l2ZTogdCA9PiB7XG4gICAgY29uc3QgY3ljbGUgPSAxLjRcbiAgICBjb25zdCBwaGFzZSA9ICh0ICUgY3ljbGUpIC8gY3ljbGVcbiAgICBjb25zdCBzdGFiID0gTWF0aC5leHAoLSgocGhhc2UgLSAwLjE1KSAqKiAyKSAqIDI2MClcbiAgICBjb25zdCBhbmdsZSA9IE1hdGguZmxvb3IodCAvIGN5Y2xlKSAqIDEuMzdcbiAgICBjb25zdCBteCA9IDAuNSArIE1hdGguY29zKGFuZ2xlKSAqIDAuNDIgKiAoc3RhYiArIDAuMTUpXG4gICAgY29uc3QgbXkgPSAwLjUgKyBNYXRoLnNpbihhbmdsZSkgKiAwLjM4ICogKHN0YWIgKyAwLjE1KVxuXG4gICAgcmV0dXJuIHsgaG92ZXI6IDAuNTUgKyBzdGFiICogMC40NSwgbXgsIG15IH1cbiAgfSxcbiAgZ2VudGxlOiB0ID0+ICh7XG4gICAgaG92ZXI6IDAuNDUgKyBNYXRoLnNpbih0ICogMC45KSAqIDAuMSxcbiAgICBteDogMC41ICsgTWF0aC5zaW4odCAqIDAuNSkgKiAwLjI4LFxuICAgIG15OiAwLjUgKyBNYXRoLmNvcyh0ICogMC4zNykgKiAwLjIyXG4gIH0pLFxuICBzbGFzaDogdCA9PiB7XG4gICAgLy8gTG9uZyBicmVhdGggLT4gc3dvcmQgc2xhc2ggLT4gcmVjb2lsIHR3aXRjaCwgcmVwZWF0aW5nLlxuICAgIGNvbnN0IGN5Y2xlID0gMy42XG4gICAgY29uc3QgcGhhc2UgPSAodCAlIGN5Y2xlKSAvIGN5Y2xlXG4gICAgY29uc3Qgc2xhc2ggPSBNYXRoLmV4cCgtKChwaGFzZSAtIDAuMjgpICoqIDIpICogMTgwKVxuICAgIGNvbnN0IG1pY3JvID0gTWF0aC5leHAoLSgocGhhc2UgLSAwLjcpICoqIDIpICogMzQwKVxuXG4gICAgY29uc3QgZHJpZnRYID0gMC41ICsgTWF0aC5zaW4odCAqIDAuNykgKiAwLjE2XG4gICAgY29uc3QgZHJpZnRZID0gMC41NSArIE1hdGguY29zKHQgKiAwLjUpICogMC4xNFxuXG4gICAgLy8gU2xhc2ggdHJhamVjdG9yeTogYm90dG9tLWxlZnQgdXAgaW50byB0aGUgZ2lhbnQncyBjaGVzdCAodG9wLXJpZ2h0KS5cbiAgICBjb25zdCBzbGFzaFggPSAtMC4xNSArIHBoYXNlICogMS41NVxuICAgIGNvbnN0IHNsYXNoWSA9IDAuOTUgLSBwaGFzZSAqIDEuMzVcblxuICAgIGNvbnN0IG14ID0gZHJpZnRYICogKDEgLSBzbGFzaCkgKyBzbGFzaFggKiBzbGFzaFxuICAgIGNvbnN0IG15ID0gZHJpZnRZICogKDEgLSBzbGFzaCkgKyBzbGFzaFkgKiBzbGFzaFxuXG4gICAgcmV0dXJuIHsgaG92ZXI6IDAuNSArIHNsYXNoICogMC41ICsgbWljcm8gKiAwLjM1LCBteCwgbXkgfVxuICB9XG59XG5cbmV4cG9ydCBmdW5jdGlvbiBJbWFnZURpc3RvcnRpb24oe1xuICBhY3RpdmUgPSB0cnVlLFxuICBhdXRvUGxheSxcbiAgY2xhc3NOYW1lLFxuICBmYWxsYmFja0NsYXNzTmFtZSxcbiAgc3JjLFxuICBzdHlsZSxcbiAgdGludCxcbiAgdGludFN0cmVuZ3RoXG59OiBJbWFnZURpc3RvcnRpb25Qcm9wcykge1xuICBjb25zdCBjYW52YXNSZWYgPSB1c2VSZWY8SFRNTENhbnZhc0VsZW1lbnQ+KG51bGwpXG4gIGNvbnN0IHRpZXIgPSB1c2VHcHVUaWVyKClcbiAgY29uc3QgW2xvYWRlZCwgc2V0TG9hZGVkXSA9IHVzZVN0YXRlKGZhbHNlKVxuXG4gIGNvbnN0IGFjdGl2ZVJlZiA9IHVzZVJlZihhY3RpdmUpXG4gIGFjdGl2ZVJlZi5jdXJyZW50ID0gYWN0aXZlXG4gIGNvbnN0IHRpbnRTdHJlbmd0aFJlZiA9IHVzZVJlZih0aW50U3RyZW5ndGgpXG4gIHRpbnRTdHJlbmd0aFJlZi5jdXJyZW50ID0gdGludFN0cmVuZ3RoXG4gIGNvbnN0IGF1dG9QbGF5UmVmID0gdXNlUmVmKGF1dG9QbGF5KVxuICBhdXRvUGxheVJlZi5jdXJyZW50ID0gYXV0b1BsYXlcblxuICBjb25zdCBzdGF0ZSA9IHVzZVJlZih7XG4gICAgYmFuZFRhcmdldHM6IG5ldyBGbG9hdDMyQXJyYXkoTlVNX0JBTkRTKSxcbiAgICBiYW5kczogbmV3IEZsb2F0MzJBcnJheShOVU1fQkFORFMpLFxuICAgIGhvdmVyVGFyZ2V0OiAwLFxuICAgIGltZ0g6IDEsXG4gICAgaW1nVzogMSxcbiAgICBteDogMC41LFxuICAgIG15OiAwLjUsXG4gICAgcHJldk14OiAwLjUsXG4gICAgcHJldk15OiAwLjUsXG4gICAgdng6IDAsXG4gICAgdnk6IDBcbiAgfSlcblxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIGlmICh0aWVyID09PSAwKSB7XG4gICAgICByZXR1cm5cbiAgICB9XG5cbiAgICBjb25zdCBjID0gY2FudmFzUmVmLmN1cnJlbnRcblxuICAgIGlmICghYykge1xuICAgICAgcmV0dXJuXG4gICAgfVxuXG4gICAgY29uc3QgZ2wgPSBjLmdldENvbnRleHQoJ3dlYmdsJylcblxuICAgIGlmICghZ2wpIHtcbiAgICAgIHJldHVyblxuICAgIH1cblxuICAgIGNvbnN0IGNvbXBpbGUgPSAodHlwZTogbnVtYmVyLCBzb3VyY2U6IHN0cmluZykgPT4ge1xuICAgICAgY29uc3QgcyA9IGdsLmNyZWF0ZVNoYWRlcih0eXBlKSFcbiAgICAgIGdsLnNoYWRlclNvdXJjZShzLCBzb3VyY2UpXG4gICAgICBnbC5jb21waWxlU2hhZGVyKHMpXG5cbiAgICAgIHJldHVybiBzXG4gICAgfVxuXG4gICAgY29uc3QgcHJvZyA9IGdsLmNyZWF0ZVByb2dyYW0oKSFcbiAgICBnbC5hdHRhY2hTaGFkZXIocHJvZywgY29tcGlsZShnbC5WRVJURVhfU0hBREVSLCBWRVJUKSlcbiAgICBnbC5hdHRhY2hTaGFkZXIocHJvZywgY29tcGlsZShnbC5GUkFHTUVOVF9TSEFERVIsIEZSQUcpKVxuICAgIGdsLmxpbmtQcm9ncmFtKHByb2cpXG4gICAgZ2wudXNlUHJvZ3JhbShwcm9nKVxuXG4gICAgZ2wuYmluZEJ1ZmZlcihnbC5BUlJBWV9CVUZGRVIsIGdsLmNyZWF0ZUJ1ZmZlcigpKVxuICAgIGdsLmJ1ZmZlckRhdGEoXG4gICAgICBnbC5BUlJBWV9CVUZGRVIsXG4gICAgICBuZXcgRmxvYXQzMkFycmF5KFstMSwgLTEsIDEsIC0xLCAtMSwgMSwgMSwgMV0pLFxuICAgICAgZ2wuU1RBVElDX0RSQVdcbiAgICApXG5cbiAgICBjb25zdCBhID0gZ2wuZ2V0QXR0cmliTG9jYXRpb24ocHJvZywgJ2EnKVxuICAgIGdsLmVuYWJsZVZlcnRleEF0dHJpYkFycmF5KGEpXG4gICAgZ2wudmVydGV4QXR0cmliUG9pbnRlcihhLCAyLCBnbC5GTE9BVCwgZmFsc2UsIDAsIDApXG5cbiAgICBjb25zdCB1VCA9IGdsLmdldFVuaWZvcm1Mb2NhdGlvbihwcm9nLCAndCcpXG4gICAgY29uc3QgdVIgPSBnbC5nZXRVbmlmb3JtTG9jYXRpb24ocHJvZywgJ3InKVxuICAgIGNvbnN0IHVJbWdTaXplID0gZ2wuZ2V0VW5pZm9ybUxvY2F0aW9uKHByb2csICdpbWdTaXplJylcbiAgICBjb25zdCB1VmVsID0gZ2wuZ2V0VW5pZm9ybUxvY2F0aW9uKHByb2csICd2ZWwnKVxuICAgIGNvbnN0IHVUZXggPSBnbC5nZXRVbmlmb3JtTG9jYXRpb24ocHJvZywgJ3RleCcpXG4gICAgY29uc3QgdVRpbnQgPSBnbC5nZXRVbmlmb3JtTG9jYXRpb24ocHJvZywgJ3RpbnQnKVxuICAgIGNvbnN0IHVUaW50U3RyZW5ndGggPSBnbC5nZXRVbmlmb3JtTG9jYXRpb24ocHJvZywgJ3RpbnRTdHJlbmd0aCcpXG4gICAgY29uc3QgdUJhbmRzOiAobnVsbCB8IFdlYkdMVW5pZm9ybUxvY2F0aW9uKVtdID0gW11cblxuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgTlVNX0JBTkRTOyBpKyspIHtcbiAgICAgIHVCYW5kcy5wdXNoKGdsLmdldFVuaWZvcm1Mb2NhdGlvbihwcm9nLCBgYmFuZHNbJHtpfV1gKSlcbiAgICB9XG5cbiAgICBjb25zdCB0ZXh0dXJlID0gZ2wuY3JlYXRlVGV4dHVyZSgpIVxuICAgIGdsLmJpbmRUZXh0dXJlKGdsLlRFWFRVUkVfMkQsIHRleHR1cmUpXG4gICAgZ2wudGV4UGFyYW1ldGVyaShnbC5URVhUVVJFXzJELCBnbC5URVhUVVJFX1dSQVBfUywgZ2wuQ0xBTVBfVE9fRURHRSlcbiAgICBnbC50ZXhQYXJhbWV0ZXJpKGdsLlRFWFRVUkVfMkQsIGdsLlRFWFRVUkVfV1JBUF9ULCBnbC5DTEFNUF9UT19FREdFKVxuICAgIGdsLnRleFBhcmFtZXRlcmkoZ2wuVEVYVFVSRV8yRCwgZ2wuVEVYVFVSRV9NSU5fRklMVEVSLCBnbC5MSU5FQVIpXG4gICAgZ2wudGV4UGFyYW1ldGVyaShnbC5URVhUVVJFXzJELCBnbC5URVhUVVJFX01BR19GSUxURVIsIGdsLkxJTkVBUilcbiAgICBnbC50ZXhJbWFnZTJEKFxuICAgICAgZ2wuVEVYVFVSRV8yRCxcbiAgICAgIDAsXG4gICAgICBnbC5SR0JBLFxuICAgICAgMSxcbiAgICAgIDEsXG4gICAgICAwLFxuICAgICAgZ2wuUkdCQSxcbiAgICAgIGdsLlVOU0lHTkVEX0JZVEUsXG4gICAgICBuZXcgVWludDhBcnJheShbMCwgMCwgMCwgMjU1XSlcbiAgICApXG5cbiAgICBjb25zdCBpbWcgPSBuZXcgSW1hZ2UoKVxuICAgIGltZy5jcm9zc09yaWdpbiA9ICdhbm9ueW1vdXMnXG5cbiAgICBpbWcub25sb2FkID0gKCkgPT4ge1xuICAgICAgc3RhdGUuY3VycmVudC5pbWdXID0gaW1nLm5hdHVyYWxXaWR0aFxuICAgICAgc3RhdGUuY3VycmVudC5pbWdIID0gaW1nLm5hdHVyYWxIZWlnaHRcbiAgICAgIGdsLmJpbmRUZXh0dXJlKGdsLlRFWFRVUkVfMkQsIHRleHR1cmUpXG4gICAgICBnbC50ZXhJbWFnZTJEKFxuICAgICAgICBnbC5URVhUVVJFXzJELFxuICAgICAgICAwLFxuICAgICAgICBnbC5SR0JBLFxuICAgICAgICBnbC5SR0JBLFxuICAgICAgICBnbC5VTlNJR05FRF9CWVRFLFxuICAgICAgICBpbWdcbiAgICAgIClcbiAgICAgIHNldExvYWRlZCh0cnVlKVxuICAgIH1cblxuICAgIGltZy5zcmMgPSBzcmNcblxuICAgIGdsLmFjdGl2ZVRleHR1cmUoZ2wuVEVYVFVSRTApXG4gICAgZ2wuYmluZFRleHR1cmUoZ2wuVEVYVFVSRV8yRCwgdGV4dHVyZSlcbiAgICBnbC51bmlmb3JtMWkodVRleCwgMClcblxuICAgIGNvbnN0IHJlc2l6ZSA9ICgpID0+IHtcbiAgICAgIGNvbnN0IHJlY3QgPSBjLmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpXG4gICAgICBjb25zdCBkcHIgPSBNYXRoLm1pbihkZXZpY2VQaXhlbFJhdGlvLCAyKVxuICAgICAgYy53aWR0aCA9IHJlY3Qud2lkdGggKiBkcHJcbiAgICAgIGMuaGVpZ2h0ID0gcmVjdC5oZWlnaHQgKiBkcHJcbiAgICAgIGdsLnZpZXdwb3J0KDAsIDAsIGMud2lkdGgsIGMuaGVpZ2h0KVxuICAgIH1cblxuICAgIHJlc2l6ZSgpXG4gICAgY29uc3Qgcm8gPSBuZXcgUmVzaXplT2JzZXJ2ZXIocmVzaXplKVxuICAgIHJvLm9ic2VydmUoYylcblxuICAgIGNvbnN0IG9uTW92ZSA9IChlOiBQb2ludGVyRXZlbnQpID0+IHtcbiAgICAgIGNvbnN0IHJlY3QgPSBjLmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpXG4gICAgICBzdGF0ZS5jdXJyZW50Lm14ID0gKGUuY2xpZW50WCAtIHJlY3QubGVmdCkgLyByZWN0LndpZHRoXG4gICAgICBzdGF0ZS5jdXJyZW50Lm15ID0gKGUuY2xpZW50WSAtIHJlY3QudG9wKSAvIHJlY3QuaGVpZ2h0XG4gICAgfVxuXG4gICAgY29uc3Qgb25FbnRlciA9ICgpID0+IHtcbiAgICAgIHN0YXRlLmN1cnJlbnQuaG92ZXJUYXJnZXQgPSAxXG4gICAgfVxuXG4gICAgY29uc3Qgb25MZWF2ZSA9ICgpID0+IHtcbiAgICAgIHN0YXRlLmN1cnJlbnQuaG92ZXJUYXJnZXQgPSAwXG4gICAgfVxuXG4gICAgLy8gV2hlbiBhdXRvUGxheSBkcml2ZXMgdGhlIGRpc3RvcnRpb24gd2Ugd2FudCB0aGUgcG9zdGVyIHRvIGxvb2tcbiAgICAvLyBhbGl2ZSByZWdhcmRsZXNzIG9mIHdoZXRoZXIgYSBwb2ludGVyIGlzIG5lYXIgdGhlIGNhbnZhcywgc28gd2VcbiAgICAvLyBza2lwIHRoZSByZWFsIHBvaW50ZXIgbGlzdGVuZXJzIGVudGlyZWx5LlxuICAgIGlmICghYXV0b1BsYXlSZWYuY3VycmVudCkge1xuICAgICAgYy5hZGRFdmVudExpc3RlbmVyKCdwb2ludGVybW92ZScsIG9uTW92ZSlcbiAgICAgIGMuYWRkRXZlbnRMaXN0ZW5lcigncG9pbnRlcmVudGVyJywgb25FbnRlcilcbiAgICAgIGMuYWRkRXZlbnRMaXN0ZW5lcigncG9pbnRlcmxlYXZlJywgb25MZWF2ZSlcbiAgICB9XG5cbiAgICBjb25zdCBiYW5kRWFzZVJhdGVzID0gbmV3IEZsb2F0MzJBcnJheShOVU1fQkFORFMpXG5cbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IE5VTV9CQU5EUzsgaSsrKSB7XG4gICAgICBiYW5kRWFzZVJhdGVzW2ldID0gMC4wMiArIE1hdGgucmFuZG9tKCkgKiAwLjA2XG4gICAgfVxuXG4gICAgY29uc3QgdGludFZlYzogcmVhZG9ubHkgW251bWJlciwgbnVtYmVyLCBudW1iZXJdID0gdGludFxuICAgICAgPyAoKCkgPT4ge1xuICAgICAgICAgIGNvbnN0IFt0ciwgdGcsIHRiXSA9IGhleFRvUmdiKHRpbnQpXG5cbiAgICAgICAgICByZXR1cm4gW3RyIC8gMjU1LCB0ZyAvIDI1NSwgdGIgLyAyNTVdIGFzIGNvbnN0XG4gICAgICAgIH0pKClcbiAgICAgIDogKFsxLCAxLCAxXSBhcyBjb25zdClcblxuICAgIGNvbnN0IHQwID0gcGVyZm9ybWFuY2Uubm93KClcbiAgICBsZXQgcmFmID0gMFxuICAgIGxldCB2aXNpYmxlID0gIWRvY3VtZW50LmhpZGRlblxuICAgIGxldCBpblZpZXcgPSB0cnVlXG5cbiAgICBjb25zdCBsb29wID0gKCkgPT4ge1xuICAgICAgcmFmID0gcmVxdWVzdEFuaW1hdGlvbkZyYW1lKGxvb3ApXG4gICAgICBjb25zdCBzID0gc3RhdGUuY3VycmVudFxuXG4gICAgICBjb25zdCBwYXR0ZXJuID0gYXV0b1BsYXlSZWYuY3VycmVudFxuICAgICAgICA/IEFVVE9QTEFZX1BBVFRFUk5TW2F1dG9QbGF5UmVmLmN1cnJlbnRdXG4gICAgICAgIDogbnVsbFxuXG4gICAgICBpZiAocGF0dGVybikge1xuICAgICAgICBjb25zdCBkcml2ZW4gPSBwYXR0ZXJuKChwZXJmb3JtYW5jZS5ub3coKSAtIHQwKSAvIDFlMylcbiAgICAgICAgcy5teCA9IGRyaXZlbi5teFxuICAgICAgICBzLm15ID0gZHJpdmVuLm15XG4gICAgICAgIHMuaG92ZXJUYXJnZXQgPSBkcml2ZW4uaG92ZXJcbiAgICAgIH1cblxuICAgICAgY29uc3QgZHZ4ID0gcy5teCAtIHMucHJldk14XG4gICAgICBjb25zdCBkdnkgPSBzLm15IC0gcy5wcmV2TXlcbiAgICAgIHMudnggKz0gKGR2eCAqIDggLSBzLnZ4KSAqIDAuMVxuICAgICAgcy52eSArPSAoZHZ5ICogOCAtIHMudnkpICogMC4xXG4gICAgICBzLnByZXZNeCA9IHMubXhcbiAgICAgIHMucHJldk15ID0gcy5teVxuXG4gICAgICBjb25zdCBzcGVlZCA9IE1hdGguc3FydChzLnZ4ICogcy52eCArIHMudnkgKiBzLnZ5KVxuXG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IE5VTV9CQU5EUzsgaSsrKSB7XG4gICAgICAgIGNvbnN0IGJhbmRDZW50ZXIgPSAoaSArIDAuNSkgLyBOVU1fQkFORFNcbiAgICAgICAgY29uc3QgZGlzdCA9IE1hdGguYWJzKHMubXkgLSBiYW5kQ2VudGVyKVxuICAgICAgICBjb25zdCBwcm94aW1pdHkgPSBNYXRoLm1heCgwLCAxIC0gZGlzdCAvIDAuMylcbiAgICAgICAgY29uc3QgYWN0aXZhdGlvbiA9XG4gICAgICAgICAgcy5ob3ZlclRhcmdldCAqIHByb3hpbWl0eSAqICgwLjQgKyBNYXRoLm1pbihzcGVlZCwgMSkgKiAwLjYpXG4gICAgICAgIHMuYmFuZFRhcmdldHNbaV0gPSBhY3RpdmF0aW9uXG4gICAgICB9XG5cbiAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgTlVNX0JBTkRTOyBpKyspIHtcbiAgICAgICAgY29uc3QgcmF0ZSA9IGJhbmRFYXNlUmF0ZXNbaV0hXG4gICAgICAgIGNvbnN0IGN1cnJlbnQgPSBzLmJhbmRzW2ldID8/IDBcbiAgICAgICAgY29uc3QgdGFyZ2V0ID0gcy5iYW5kVGFyZ2V0c1tpXSA/PyAwXG4gICAgICAgIHMuYmFuZHNbaV0gPSBjdXJyZW50ICsgKHRhcmdldCAtIGN1cnJlbnQpICogcmF0ZVxuXG4gICAgICAgIGlmIChzLmJhbmRzW2ldISA8IDAuMDAxKSB7XG4gICAgICAgICAgcy5iYW5kc1tpXSA9IDBcbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICBnbC51bmlmb3JtMWYodVQsIChwZXJmb3JtYW5jZS5ub3coKSAtIHQwKSAvIDFlMylcbiAgICAgIGdsLnVuaWZvcm0yZih1UiwgYy53aWR0aCwgYy5oZWlnaHQpXG4gICAgICBnbC51bmlmb3JtMmYodUltZ1NpemUsIHMuaW1nVywgcy5pbWdIKVxuICAgICAgZ2wudW5pZm9ybTJmKHVWZWwsIHMudngsIHMudnkpXG4gICAgICBnbC51bmlmb3JtM2YodVRpbnQsIHRpbnRWZWNbMF0sIHRpbnRWZWNbMV0sIHRpbnRWZWNbMl0pXG5cbiAgICAgIGNvbnN0IHRzID0gdGludFN0cmVuZ3RoUmVmLmN1cnJlbnRcbiAgICAgIGNvbnN0IGRlZmF1bHRTdHJlbmd0aCA9IHRpbnQgPyAwLjM1IDogMFxuICAgICAgY29uc3QgZGVmYXVsdEluYWN0aXZlID0gdGludCA/IDAuMTUgOiAwXG4gICAgICBnbC51bmlmb3JtMWYoXG4gICAgICAgIHVUaW50U3RyZW5ndGgsXG4gICAgICAgIGFjdGl2ZVJlZi5jdXJyZW50XG4gICAgICAgICAgPyAodHM/LmFjdGl2ZSA/PyBkZWZhdWx0U3RyZW5ndGgpXG4gICAgICAgICAgOiAodHM/LmluYWN0aXZlID8/IGRlZmF1bHRJbmFjdGl2ZSlcbiAgICAgIClcblxuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCBOVU1fQkFORFM7IGkrKykge1xuICAgICAgICBnbC51bmlmb3JtMWYodUJhbmRzW2ldISwgcy5iYW5kc1tpXSEpXG4gICAgICB9XG5cbiAgICAgIGdsLmJpbmRUZXh0dXJlKGdsLlRFWFRVUkVfMkQsIHRleHR1cmUpXG4gICAgICBnbC5kcmF3QXJyYXlzKGdsLlRSSUFOR0xFX1NUUklQLCAwLCA0KVxuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0ID0gKCkgPT4ge1xuICAgICAgaWYgKHZpc2libGUgJiYgaW5WaWV3ICYmICFyYWYpIHtcbiAgICAgICAgcmFmID0gcmVxdWVzdEFuaW1hdGlvbkZyYW1lKGxvb3ApXG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3Qgc3RvcCA9ICgpID0+IHtcbiAgICAgIGlmIChyYWYpIHtcbiAgICAgICAgY2FuY2VsQW5pbWF0aW9uRnJhbWUocmFmKVxuICAgICAgICByYWYgPSAwXG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3Qgb25WaXNpYmlsaXR5ID0gKCkgPT4ge1xuICAgICAgdmlzaWJsZSA9ICFkb2N1bWVudC5oaWRkZW5cbiAgICAgIHZpc2libGUgPyBzdGFydCgpIDogc3RvcCgpXG4gICAgfVxuXG4gICAgY29uc3QgaW8gPSBuZXcgSW50ZXJzZWN0aW9uT2JzZXJ2ZXIoXG4gICAgICBlbnRyaWVzID0+IHtcbiAgICAgICAgaW5WaWV3ID0gZW50cmllcy5zb21lKGUgPT4gZS5pc0ludGVyc2VjdGluZylcbiAgICAgICAgaW5WaWV3ID8gc3RhcnQoKSA6IHN0b3AoKVxuICAgICAgfSxcbiAgICAgIHsgdGhyZXNob2xkOiAwIH1cbiAgICApXG5cbiAgICBpby5vYnNlcnZlKGMpXG4gICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcigndmlzaWJpbGl0eWNoYW5nZScsIG9uVmlzaWJpbGl0eSlcblxuICAgIHN0YXJ0KClcblxuICAgIHJldHVybiAoKSA9PiB7XG4gICAgICBzdG9wKClcbiAgICAgIGlvLmRpc2Nvbm5lY3QoKVxuICAgICAgZG9jdW1lbnQucmVtb3ZlRXZlbnRMaXN0ZW5lcigndmlzaWJpbGl0eWNoYW5nZScsIG9uVmlzaWJpbGl0eSlcbiAgICAgIHJvLmRpc2Nvbm5lY3QoKVxuICAgICAgYy5yZW1vdmVFdmVudExpc3RlbmVyKCdwb2ludGVybW92ZScsIG9uTW92ZSlcbiAgICAgIGMucmVtb3ZlRXZlbnRMaXN0ZW5lcigncG9pbnRlcmVudGVyJywgb25FbnRlcilcbiAgICAgIGMucmVtb3ZlRXZlbnRMaXN0ZW5lcigncG9pbnRlcmxlYXZlJywgb25MZWF2ZSlcbiAgICAgIGdsLmRlbGV0ZVRleHR1cmUodGV4dHVyZSlcbiAgICAgIGdsLmRlbGV0ZVByb2dyYW0ocHJvZylcbiAgICAgIHNldExvYWRlZChmYWxzZSlcbiAgICB9XG4gICAgLy8gYXV0b1BsYXkgaXMgaW50ZW50aW9uYWxseSBvbWl0dGVkIHNvIHRvZ2dsaW5nIGl0IGF0IHJ1bnRpbWUgZG9lc24ndFxuICAgIC8vIHRlYXIgZG93biB0aGUgc2hhZGVyIHBpcGVsaW5lLiBUaGUgcmVmLWRyaXZlbiBsb29wIHJlYWRzIHRoZSBsaXZlXG4gICAgLy8gdmFsdWUgZWFjaCBmcmFtZSwgc28gbGlzdGVuZXIgYXR0YWNoL2RldGFjaCBpcyBoYW5kbGVkIG9uY2Ugb24gbW91bnQuXG4gICAgLy8gZXNsaW50LWRpc2FibGUtbmV4dC1saW5lIHJlYWN0LWhvb2tzL2V4aGF1c3RpdmUtZGVwc1xuICB9LCBbc3JjLCB0aWVyLCB0aW50XSlcblxuICBpZiAodGllciA9PT0gMCkge1xuICAgIHJldHVybiAoXG4gICAgICAvLyBlc2xpbnQtZGlzYWJsZS1uZXh0LWxpbmUgQG5leHQvbmV4dC9uby1pbWctZWxlbWVudFxuICAgICAgPGltZ1xuICAgICAgICBhbHQ9XCJcIlxuICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICdhYnNvbHV0ZSBpbnNldC0wIGgtZnVsbCB3LWZ1bGwgb2JqZWN0LWNvdmVyJyxcbiAgICAgICAgICBmYWxsYmFja0NsYXNzTmFtZSA/PyBjbGFzc05hbWVcbiAgICAgICAgKX1cbiAgICAgICAgZmV0Y2hQcmlvcml0eT1cImhpZ2hcIlxuICAgICAgICBzcmM9e3NyY31cbiAgICAgICAgc3R5bGU9e3sgbWl4QmxlbmRNb2RlOiAnb3ZlcmxheScsIC4uLnN0eWxlIH19XG4gICAgICAvPlxuICAgIClcbiAgfVxuXG4gIHJldHVybiAoXG4gICAgPGNhbnZhc1xuICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgJ2Fic29sdXRlIGluc2V0LTAgaC1mdWxsIHctZnVsbCB0cmFuc2l0aW9uLW9wYWNpdHkgZHVyYXRpb24tNTAwJyxcbiAgICAgICAgY2xhc3NOYW1lXG4gICAgICApfVxuICAgICAgcmVmPXtjYW52YXNSZWZ9XG4gICAgICBzdHlsZT17e1xuICAgICAgICBtaXhCbGVuZE1vZGU6ICdvdmVybGF5JyxcbiAgICAgICAgb3BhY2l0eTogbG9hZGVkID8gMSA6IDAsXG4gICAgICAgIC4uLnN0eWxlXG4gICAgICB9fVxuICAgIC8+XG4gIClcbn1cblxuZXhwb3J0IHR5cGUgQXV0b1BsYXlQYXR0ZXJuID0gJ2FnZ3Jlc3NpdmUnIHwgJ2dlbnRsZScgfCAnc2xhc2gnXG5cbmludGVyZmFjZSBJbWFnZURpc3RvcnRpb25Qcm9wcyB7XG4gIGFjdGl2ZT86IGJvb2xlYW5cbiAgLyoqXG4gICAqIERyaXZlIHRoZSBkaXN0b3J0aW9uIHdpdGggYSBjaG9yZW9ncmFwaGVkIG1vdGlvbiBwYXR0ZXJuIGluc3RlYWQgb2ZcbiAgICogd2FpdGluZyBmb3IgYSByZWFsIHBvaW50ZXIuIFVzZWZ1bCBmb3IgcG9zdGVycywgc29jaWFsIGNsaXBzLCBhbmQgYW55XG4gICAqIGNvbnRleHQgd2hlcmUgdGhlIGltYWdlIG5lZWRzIHRvIGZlZWwgYWxpdmUgb24gaXRzIG93bi5cbiAgICovXG4gIGF1dG9QbGF5PzogQXV0b1BsYXlQYXR0ZXJuXG4gIGNsYXNzTmFtZT86IHN0cmluZ1xuICBmYWxsYmFja0NsYXNzTmFtZT86IHN0cmluZ1xuICBzcmM6IHN0cmluZ1xuICBzdHlsZT86IFJlYWN0LkNTU1Byb3BlcnRpZXNcbiAgdGludD86IHN0cmluZ1xuICB0aW50U3RyZW5ndGg/OiB7IGFjdGl2ZTogbnVtYmVyOyBpbmFjdGl2ZTogbnVtYmVyIH1cbn1cbiJd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
