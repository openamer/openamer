"use client";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import fillerBg from "../../assets/filler-bg0.webp";
import { cn } from "../../utils/index.js";
import { Blink } from "./blink.js";
import { ImageDistortion } from "./image-distortion.js";
import { Typography } from "./typography/index.js";
import { Small } from "./typography/small.js";
const ASPECT_CONFIG = {
  landscape: { defaultLayout: "split", height: 1080, width: 1920 },
  portrait: { defaultLayout: "split", height: 1350, width: 1080 },
  square: { defaultLayout: "split", height: 1080, width: 1080 },
  story: { defaultLayout: "stacked", height: 1920, width: 1080 },
  wide: { defaultLayout: "split", height: 900, width: 1600 }
};
const DEFAULT_SRC = fillerBg.src ?? fillerBg;
function useUtcClock() {
  const [now, setNow] = useState(null);
  useEffect(() => {
    setNow(/* @__PURE__ */ new Date());
    const id = setInterval(() => setNow(/* @__PURE__ */ new Date()), 1e3);
    return () => clearInterval(id);
  }, []);
  return now ? now.toISOString().slice(11, 19) : "--:--:--";
}
function CornerMark({ className }) {
  return /* @__PURE__ */ jsxs(
    "span",
    {
      "aria-hidden": true,
      className: cn(
        "pointer-events-none absolute block size-4 opacity-50",
        className
      ),
      children: [
        /* @__PURE__ */ jsx("span", { className: "absolute top-1/2 left-0 h-px w-full -translate-y-1/2 bg-current" }),
        /* @__PURE__ */ jsx("span", { className: "absolute top-0 left-1/2 h-full w-px -translate-x-1/2 bg-current" })
      ]
    }
  );
}
function ChannelDot() {
  return /* @__PURE__ */ jsxs("span", { className: "flex items-center gap-1.5", children: [
    /* @__PURE__ */ jsx("span", { className: "bg-midground size-1.5 animate-pulse rounded-full" }),
    /* @__PURE__ */ jsx(Small, { className: "opacity-70", children: "REC" })
  ] });
}
function ScanlineOverlay() {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "aria-hidden": true,
      className: "pointer-events-none absolute inset-0 opacity-20 mix-blend-overlay",
      style: {
        backgroundImage: "repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(255,255,255,0.08) 2px, rgba(255,255,255,0.08) 3px)"
      }
    }
  );
}
export function Poster({
  aspect = "square",
  autoPlay = "slash",
  body,
  border = true,
  channel,
  children,
  className,
  cornerMarks = true,
  eyebrow,
  headline = ["An Agent", "That Grows", "With You."],
  layout,
  scale = 1,
  seal = "MIT \xB7 2026",
  signature,
  src = DEFAULT_SRC,
  tags,
  tint,
  tintStrength,
  variant = "vibe",
  ...rest
}) {
  const config = ASPECT_CONFIG[aspect];
  const resolvedLayout = layout ?? config.defaultLayout;
  const outerProps = {
    // `text-midground` (not `text-foreground`) is the readable on-canvas
    // color across every lens. `--foreground` is really the lens's inversion
    // layer color: on dark lenses it has `fgOpacity: 0` and resolves to
    // fully-transparent via `color-mix`, which would make text invisible.
    // `--midground` always has opacity 1 and picks up each lens's accent.
    className: cn(
      "text-midground relative overflow-hidden font-sans",
      border && "border border-current/25",
      className
    ),
    style: {
      aspectRatio: `${config.width} / ${config.height}`,
      background: "var(--background)",
      containerType: "inline-size",
      fontSize: `${16 / config.width * 100}cqi`,
      maxHeight: "calc(100dvh - 8rem)",
      maxWidth: "100%",
      width: `${config.width * scale}px`
    },
    ...rest
  };
  if (variant === "vibe") {
    return /* @__PURE__ */ jsx("div", { ...outerProps, children: /* @__PURE__ */ jsx(
      VibeContent,
      {
        autoPlay,
        channel,
        cornerMarks,
        signature,
        src,
        tint,
        tintStrength
      }
    ) });
  }
  const headlineLines = Array.isArray(headline) ? headline : [headline];
  return /* @__PURE__ */ jsxs("div", { ...outerProps, className: cn("flex flex-col", outerProps.className), children: [
    /* @__PURE__ */ jsx(DispatchHeader, { channel }),
    /* @__PURE__ */ jsxs(
      "div",
      {
        className: cn(
          "relative min-h-0 min-w-0 flex-1",
          resolvedLayout === "split" ? "grid grid-cols-[3fr_2fr]" : "grid grid-rows-[3fr_2fr]"
        ),
        children: [
          /* @__PURE__ */ jsxs(
            "div",
            {
              className: cn(
                "relative overflow-hidden border-current/20",
                resolvedLayout === "split" ? "border-r" : "border-b"
              ),
              style: { backgroundColor: "var(--background)" },
              children: [
                /* @__PURE__ */ jsx(
                  ImageDistortion,
                  {
                    autoPlay,
                    src,
                    tint,
                    tintStrength
                  }
                ),
                cornerMarks && /* @__PURE__ */ jsxs(Fragment, { children: [
                  /* @__PURE__ */ jsx(CornerMark, { className: "top-3 left-3" }),
                  /* @__PURE__ */ jsx(CornerMark, { className: "top-3 right-3" }),
                  /* @__PURE__ */ jsx(CornerMark, { className: "bottom-3 left-3" }),
                  /* @__PURE__ */ jsx(CornerMark, { className: "right-3 bottom-3" })
                ] }),
                /* @__PURE__ */ jsx(ScanlineOverlay, {}),
                /* @__PURE__ */ jsx(Small, { className: "absolute bottom-4 left-4 z-1 opacity-80", children: "OpenAmer Agent" })
              ]
            }
          ),
          /* @__PURE__ */ jsxs("aside", { className: "relative flex min-w-0 flex-col justify-between gap-8 p-8", children: [
            /* @__PURE__ */ jsxs("div", { className: "flex flex-col gap-5", children: [
              eyebrow && /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
                /* @__PURE__ */ jsx("span", { className: "bg-midground/80 h-px flex-1" }),
                /* @__PURE__ */ jsx(Small, { className: "opacity-80", children: eyebrow })
              ] }),
              children ?? /* @__PURE__ */ jsxs(Fragment, { children: [
                /* @__PURE__ */ jsx(
                  Typography,
                  {
                    as: "h1",
                    className: "text-[2.75em] leading-[0.95] font-bold tracking-[-0.01em]",
                    expanded: true,
                    children: headlineLines.map((line, i) => /* @__PURE__ */ jsx("span", { className: "block", children: line }, `${line}-${i}`))
                  }
                ),
                body && /* @__PURE__ */ jsx("p", { className: "text-[1.0625em] leading-[1.5] tracking-normal normal-case opacity-60", children: body })
              ] })
            ] }),
            tags && tags.length > 0 && /* @__PURE__ */ jsx("ul", { className: "flex flex-col gap-2 border-t border-current/15 pt-4", children: tags.map((tag, i) => /* @__PURE__ */ jsxs(
              "li",
              {
                className: "flex items-baseline justify-between gap-3",
                children: [
                  /* @__PURE__ */ jsx(Small, { className: "font-courier opacity-40", children: String(i + 1).padStart(3, "0") }),
                  /* @__PURE__ */ jsx(Small, { className: "opacity-80", children: tag }),
                  /* @__PURE__ */ jsx("span", { className: "mx-1 h-px flex-1 translate-y-[-3px] border-b border-dotted border-current/25" }),
                  /* @__PURE__ */ jsxs(Small, { className: "font-courier opacity-40", children: [
                    String(i + 1).padStart(2, "0"),
                    "/",
                    String(tags.length).padStart(2, "0")
                  ] })
                ]
              },
              `${tag}-${i}`
            )) })
          ] })
        ]
      }
    ),
    /* @__PURE__ */ jsxs("footer", { className: "flex items-center justify-between gap-4 border-t border-current/20 px-6 py-3", children: [
      /* @__PURE__ */ jsxs(Small, { className: "opacity-70", children: [
        signature,
        /* @__PURE__ */ jsx(Blink, {})
      ] }),
      /* @__PURE__ */ jsx(Small, { className: "font-courier opacity-40", children: seal })
    ] })
  ] });
}
function DispatchHeader({ channel }) {
  const clock = useUtcClock();
  return /* @__PURE__ */ jsxs("header", { className: "flex items-center justify-between gap-4 border-b border-current/20 px-6 py-3", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
      /* @__PURE__ */ jsx("span", { className: "bg-midground size-2 rounded-sm opacity-70" }),
      /* @__PURE__ */ jsx(Small, { className: "opacity-70", children: channel })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-4", children: [
      /* @__PURE__ */ jsx(ChannelDot, {}),
      /* @__PURE__ */ jsxs(Small, { className: "font-courier opacity-50", children: [
        clock,
        " UTC"
      ] })
    ] })
  ] });
}
function VibeContent({
  autoPlay,
  channel,
  cornerMarks,
  signature,
  src,
  tint,
  tintStrength
}) {
  return /* @__PURE__ */ jsxs("div", { className: "absolute inset-0", children: [
    /* @__PURE__ */ jsx(
      ImageDistortion,
      {
        autoPlay,
        src,
        tint,
        tintStrength
      }
    ),
    cornerMarks && /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx(CornerMark, { className: "top-5 left-5" }),
      /* @__PURE__ */ jsx(CornerMark, { className: "top-5 right-5" }),
      /* @__PURE__ */ jsx(CornerMark, { className: "bottom-5 left-5" }),
      /* @__PURE__ */ jsx(CornerMark, { className: "right-5 bottom-5" })
    ] }),
    /* @__PURE__ */ jsx(ScanlineOverlay, {}),
    channel && /* @__PURE__ */ jsx(Small, { className: "absolute top-5 left-10 z-1 text-[0.75em] opacity-70", children: channel }),
    /* @__PURE__ */ jsx(Small, { className: "absolute right-10 bottom-5 z-1 text-[0.75em] opacity-80", children: signature })
  ] });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZUVmZmVjdCwgdXNlU3RhdGUgfSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IGZpbGxlckJnIGZyb20gJy4uLy4uL2Fzc2V0cy9maWxsZXItYmcwLndlYnAnXG5pbXBvcnQgeyBjbiB9IGZyb20gJy4uLy4uL3V0aWxzJ1xuXG5pbXBvcnQgeyBCbGluayB9IGZyb20gJy4vYmxpbmsnXG5pbXBvcnQgeyBJbWFnZURpc3RvcnRpb24gfSBmcm9tICcuL2ltYWdlLWRpc3RvcnRpb24nXG5pbXBvcnQgeyBUeXBvZ3JhcGh5IH0gZnJvbSAnLi90eXBvZ3JhcGh5J1xuaW1wb3J0IHsgU21hbGwgfSBmcm9tICcuL3R5cG9ncmFwaHkvc21hbGwnXG5cbmltcG9ydCB0eXBlIHsgQXV0b1BsYXlQYXR0ZXJuIH0gZnJvbSAnLi9pbWFnZS1kaXN0b3J0aW9uJ1xuXG5jb25zdCBBU1BFQ1RfQ09ORklHOiBSZWNvcmQ8XG4gIFBvc3RlckFzcGVjdCxcbiAgeyBkZWZhdWx0TGF5b3V0OiAnc3BsaXQnIHwgJ3N0YWNrZWQnOyBoZWlnaHQ6IG51bWJlcjsgd2lkdGg6IG51bWJlciB9XG4+ID0ge1xuICBsYW5kc2NhcGU6IHsgZGVmYXVsdExheW91dDogJ3NwbGl0JywgaGVpZ2h0OiAxMDgwLCB3aWR0aDogMTkyMCB9LFxuICBwb3J0cmFpdDogeyBkZWZhdWx0TGF5b3V0OiAnc3BsaXQnLCBoZWlnaHQ6IDEzNTAsIHdpZHRoOiAxMDgwIH0sXG4gIHNxdWFyZTogeyBkZWZhdWx0TGF5b3V0OiAnc3BsaXQnLCBoZWlnaHQ6IDEwODAsIHdpZHRoOiAxMDgwIH0sXG4gIHN0b3J5OiB7IGRlZmF1bHRMYXlvdXQ6ICdzdGFja2VkJywgaGVpZ2h0OiAxOTIwLCB3aWR0aDogMTA4MCB9LFxuICB3aWRlOiB7IGRlZmF1bHRMYXlvdXQ6ICdzcGxpdCcsIGhlaWdodDogOTAwLCB3aWR0aDogMTYwMCB9XG59XG5cbmNvbnN0IERFRkFVTFRfU1JDID1cbiAgKGZpbGxlckJnIGFzIHsgc3JjPzogc3RyaW5nIH0pLnNyYyA/PyAoZmlsbGVyQmcgYXMgdW5rbm93biBhcyBzdHJpbmcpXG5cbmZ1bmN0aW9uIHVzZVV0Y0Nsb2NrKCkge1xuICBjb25zdCBbbm93LCBzZXROb3ddID0gdXNlU3RhdGU8RGF0ZSB8IG51bGw+KG51bGwpXG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBzZXROb3cobmV3IERhdGUoKSlcbiAgICBjb25zdCBpZCA9IHNldEludGVydmFsKCgpID0+IHNldE5vdyhuZXcgRGF0ZSgpKSwgMTAwMClcblxuICAgIHJldHVybiAoKSA9PiBjbGVhckludGVydmFsKGlkKVxuICB9LCBbXSlcblxuICByZXR1cm4gbm93ID8gbm93LnRvSVNPU3RyaW5nKCkuc2xpY2UoMTEsIDE5KSA6ICctLTotLTotLSdcbn1cblxuZnVuY3Rpb24gQ29ybmVyTWFyayh7IGNsYXNzTmFtZSB9OiB7IGNsYXNzTmFtZT86IHN0cmluZyB9KSB7XG4gIHJldHVybiAoXG4gICAgPHNwYW5cbiAgICAgIGFyaWEtaGlkZGVuXG4gICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAncG9pbnRlci1ldmVudHMtbm9uZSBhYnNvbHV0ZSBibG9jayBzaXplLTQgb3BhY2l0eS01MCcsXG4gICAgICAgIGNsYXNzTmFtZVxuICAgICAgKX1cbiAgICA+XG4gICAgICA8c3BhbiBjbGFzc05hbWU9XCJhYnNvbHV0ZSB0b3AtMS8yIGxlZnQtMCBoLXB4IHctZnVsbCAtdHJhbnNsYXRlLXktMS8yIGJnLWN1cnJlbnRcIiAvPlxuXG4gICAgICA8c3BhbiBjbGFzc05hbWU9XCJhYnNvbHV0ZSB0b3AtMCBsZWZ0LTEvMiBoLWZ1bGwgdy1weCAtdHJhbnNsYXRlLXgtMS8yIGJnLWN1cnJlbnRcIiAvPlxuICAgIDwvc3Bhbj5cbiAgKVxufVxuXG5mdW5jdGlvbiBDaGFubmVsRG90KCkge1xuICByZXR1cm4gKFxuICAgIDxzcGFuIGNsYXNzTmFtZT1cImZsZXggaXRlbXMtY2VudGVyIGdhcC0xLjVcIj5cbiAgICAgIDxzcGFuIGNsYXNzTmFtZT1cImJnLW1pZGdyb3VuZCBzaXplLTEuNSBhbmltYXRlLXB1bHNlIHJvdW5kZWQtZnVsbFwiIC8+XG5cbiAgICAgIDxTbWFsbCBjbGFzc05hbWU9XCJvcGFjaXR5LTcwXCI+UkVDPC9TbWFsbD5cbiAgICA8L3NwYW4+XG4gIClcbn1cblxuZnVuY3Rpb24gU2NhbmxpbmVPdmVybGF5KCkge1xuICByZXR1cm4gKFxuICAgIDxkaXZcbiAgICAgIGFyaWEtaGlkZGVuXG4gICAgICBjbGFzc05hbWU9XCJwb2ludGVyLWV2ZW50cy1ub25lIGFic29sdXRlIGluc2V0LTAgb3BhY2l0eS0yMCBtaXgtYmxlbmQtb3ZlcmxheVwiXG4gICAgICBzdHlsZT17e1xuICAgICAgICBiYWNrZ3JvdW5kSW1hZ2U6XG4gICAgICAgICAgJ3JlcGVhdGluZy1saW5lYXItZ3JhZGllbnQoMGRlZywgdHJhbnNwYXJlbnQgMCwgdHJhbnNwYXJlbnQgMnB4LCByZ2JhKDI1NSwyNTUsMjU1LDAuMDgpIDJweCwgcmdiYSgyNTUsMjU1LDI1NSwwLjA4KSAzcHgpJ1xuICAgICAgfX1cbiAgICAvPlxuICApXG59XG5cbi8qKlxuICogU29jaWFsLXJlYWR5IGdsaXRjaHkgY2FyZCBidWlsdCBhcm91bmQgdGhlIGhhcHRpYy1kaXN0b3J0aW9uIGltYWdlXG4gKiBjb21wb25lbnQuIFRoZSBwb3N0ZXIgcnVucyB0aGUgc3dvcmQtZ3V5IGRpc3RvcnRpb24gb24gYW4gYXV0by1hbmltYXRlZFxuICogc2xhc2ggcGF0dGVybiBzbyBpdCBjYW4gYmUgc2NyZWVuLXJlY29yZGVkIGFzIGEgR0lGIHdpdGhvdXQgYSBodW1hblxuICogbW92aW5nIGEgY3Vyc29yLlxuICpcbiAqIFR3byB2YXJpYW50cywgbWF0Y2hpbmcgYWN0dWFsIHVzZSBjYXNlczpcbiAqIC0gYCd2aWJlJ2AgKGRlZmF1bHQpOiBmdWxsLWJsZWVkIGRpc3RvcnRlZCBpbWFnZSB3aXRoIGp1c3QgcmVnaXN0cmF0aW9uXG4gKiAgIG1hcmtzIGFuZCBhIHRpbnkgXCJIZXJtZXMgQWdlbnRcIiBtYXJrIGluIHRoZSBjb3JuZXIgXHUyMDE0IG1pcnJvcnMgdGhlXG4gKiAgIG92ZXJsYXkgb24gdGhlIEhlcm1lcyBhZ2VudCB3ZWJzaXRlLlxuICogLSBgJ2Rpc3BhdGNoJ2A6IGJyb2FkY2FzdC1jYXJkIGxheW91dCB3aXRoIHNpZGViYXIgY29weSwgbnVtYmVyZWQgdGFncyxcbiAqICAgYW5kIGNocm9tZSBcdTIwMTQgZm9yIHdoZW4gdGhlIHBvc3RlciBuZWVkcyB0byBjYXJyeSBpbmZvcm1hdGlvbi5cbiAqL1xuZXhwb3J0IGZ1bmN0aW9uIFBvc3Rlcih7XG4gIGFzcGVjdCA9ICdzcXVhcmUnLFxuICBhdXRvUGxheSA9ICdzbGFzaCcsXG4gIGJvZHksXG4gIGJvcmRlciA9IHRydWUsXG4gIGNoYW5uZWwsXG4gIGNoaWxkcmVuLFxuICBjbGFzc05hbWUsXG4gIGNvcm5lck1hcmtzID0gdHJ1ZSxcbiAgZXllYnJvdyxcbiAgaGVhZGxpbmUgPSBbJ0FuIEFnZW50JywgJ1RoYXQgR3Jvd3MnLCAnV2l0aCBZb3UuJ10sXG4gIGxheW91dCxcbiAgc2NhbGUgPSAxLFxuICBzZWFsID0gJ01JVCBcdTAwQjcgMjAyNicsXG4gIHNpZ25hdHVyZSxcbiAgc3JjID0gREVGQVVMVF9TUkMsXG4gIHRhZ3MsXG4gIHRpbnQsXG4gIHRpbnRTdHJlbmd0aCxcbiAgdmFyaWFudCA9ICd2aWJlJyxcbiAgLi4ucmVzdFxufTogUG9zdGVyUHJvcHMpIHtcbiAgY29uc3QgY29uZmlnID0gQVNQRUNUX0NPTkZJR1thc3BlY3RdXG4gIGNvbnN0IHJlc29sdmVkTGF5b3V0ID0gbGF5b3V0ID8/IGNvbmZpZy5kZWZhdWx0TGF5b3V0XG5cbiAgLy8gVXNlIGFzcGVjdC1yYXRpbyArIG1heC13aWR0aC9oZWlnaHQgc28gdGhlIHBvc3RlciBmbHVpZGx5IGZpdHMgYW55IHBhcmVudFxuICAvLyAoc3Rvcnlib29rIGlmcmFtZSwgYSB0d2VldCBwcmV2aWV3LCBhbiBlbWJlZCkgd2l0aG91dCBnZXR0aW5nIGNsaXBwZWQsXG4gIC8vIGJ1dCBjYXBzIGF0IHRoZSBpbnRlbmRlZCBleHBvcnQgd2lkdGggZm9yIHNjcmVlbi1yZWNvcmRpbmcuIGBtYXhIZWlnaHRgXG4gIC8vIHVzZXMgYW4gYWJzb2x1dGUgYGR2aGAtYmFzZWQgdmFsdWUgcmF0aGVyIHRoYW4gYCVgIGJlY2F1c2UgYCVgIGluc2lkZSBhXG4gIC8vIGZsZXggY29udGFpbmVyIGNhbiBjYXVzZSB0aGUgYnJvd3NlciB0byBjbGFtcCBoZWlnaHQgd2l0aG91dCByZS1ydW5uaW5nXG4gIC8vIGFzcGVjdC1yYXRpbyBvbiB3aWR0aCwgcHJvZHVjaW5nIGEgc3VidGx5IHdyb25nIHNoYXBlLiBBbiBhYnNvbHV0ZSBjYXBcbiAgLy8gbGVhdmVzIGFzcGVjdC1yYXRpbyBmdWxseSBpbiBjaGFyZ2U6IG9uY2UgdGhlIGhlaWdodCBiaW5kcywgd2lkdGggaXNcbiAgLy8gcmUtZGVyaXZlZCBjb3JyZWN0bHkuIGBjYWxjKDEwMGR2aCAtIDhyZW0pYCA9IHZpZXdwb3J0IG1pbnVzIGEgdHlwaWNhbFxuICAvLyBob3N0J3MgdmVydGljYWwgcGFkZGluZyAoZS5nLiBTdG9yeWJvb2sncyBgcC04YCA9IDRyZW0gb24gZWFjaCBzaWRlKSxcbiAgLy8gc28gdGhlIHBvc3RlciArIHBhZGRpbmcgZml0IHdpdGhpbiB0aGUgdmlld3BvcnQgd2l0aG91dCBldmVyIHByb2R1Y2luZ1xuICAvLyBzY3JvbGxiYXJzLiBDb250YWluZXIgcXVlcmllcyB0aWUgYWxsIGludGVybmFsIHR5cG9ncmFwaHkgdG8gdGhlXG4gIC8vIGFjdHVhbCByZW5kZXJlZCB3aWR0aCBzbyBoZWFkbGluZS9tZXRhZGF0YSBzY2FsZXMgYWxvbmcgd2l0aCB0aGUgY2FudmFzLlxuICBjb25zdCBvdXRlclByb3BzID0ge1xuICAgIC8vIGB0ZXh0LW1pZGdyb3VuZGAgKG5vdCBgdGV4dC1mb3JlZ3JvdW5kYCkgaXMgdGhlIHJlYWRhYmxlIG9uLWNhbnZhc1xuICAgIC8vIGNvbG9yIGFjcm9zcyBldmVyeSBsZW5zLiBgLS1mb3JlZ3JvdW5kYCBpcyByZWFsbHkgdGhlIGxlbnMncyBpbnZlcnNpb25cbiAgICAvLyBsYXllciBjb2xvcjogb24gZGFyayBsZW5zZXMgaXQgaGFzIGBmZ09wYWNpdHk6IDBgIGFuZCByZXNvbHZlcyB0b1xuICAgIC8vIGZ1bGx5LXRyYW5zcGFyZW50IHZpYSBgY29sb3ItbWl4YCwgd2hpY2ggd291bGQgbWFrZSB0ZXh0IGludmlzaWJsZS5cbiAgICAvLyBgLS1taWRncm91bmRgIGFsd2F5cyBoYXMgb3BhY2l0eSAxIGFuZCBwaWNrcyB1cCBlYWNoIGxlbnMncyBhY2NlbnQuXG4gICAgY2xhc3NOYW1lOiBjbihcbiAgICAgICd0ZXh0LW1pZGdyb3VuZCByZWxhdGl2ZSBvdmVyZmxvdy1oaWRkZW4gZm9udC1zYW5zJyxcbiAgICAgIGJvcmRlciAmJiAnYm9yZGVyIGJvcmRlci1jdXJyZW50LzI1JyxcbiAgICAgIGNsYXNzTmFtZVxuICAgICksXG4gICAgc3R5bGU6IHtcbiAgICAgIGFzcGVjdFJhdGlvOiBgJHtjb25maWcud2lkdGh9IC8gJHtjb25maWcuaGVpZ2h0fWAsXG4gICAgICBiYWNrZ3JvdW5kOiAndmFyKC0tYmFja2dyb3VuZCknLFxuICAgICAgY29udGFpbmVyVHlwZTogJ2lubGluZS1zaXplJyBhcyBjb25zdCxcbiAgICAgIGZvbnRTaXplOiBgJHsoMTYgLyBjb25maWcud2lkdGgpICogMTAwfWNxaWAsXG4gICAgICBtYXhIZWlnaHQ6ICdjYWxjKDEwMGR2aCAtIDhyZW0pJyxcbiAgICAgIG1heFdpZHRoOiAnMTAwJScsXG4gICAgICB3aWR0aDogYCR7Y29uZmlnLndpZHRoICogc2NhbGV9cHhgXG4gICAgfSxcbiAgICAuLi5yZXN0XG4gIH1cblxuICBpZiAodmFyaWFudCA9PT0gJ3ZpYmUnKSB7XG4gICAgcmV0dXJuIChcbiAgICAgIDxkaXYgey4uLm91dGVyUHJvcHN9PlxuICAgICAgICA8VmliZUNvbnRlbnRcbiAgICAgICAgICBhdXRvUGxheT17YXV0b1BsYXl9XG4gICAgICAgICAgY2hhbm5lbD17Y2hhbm5lbH1cbiAgICAgICAgICBjb3JuZXJNYXJrcz17Y29ybmVyTWFya3N9XG4gICAgICAgICAgc2lnbmF0dXJlPXtzaWduYXR1cmV9XG4gICAgICAgICAgc3JjPXtzcmN9XG4gICAgICAgICAgdGludD17dGludH1cbiAgICAgICAgICB0aW50U3RyZW5ndGg9e3RpbnRTdHJlbmd0aH1cbiAgICAgICAgLz5cbiAgICAgIDwvZGl2PlxuICAgIClcbiAgfVxuXG4gIGNvbnN0IGhlYWRsaW5lTGluZXMgPSBBcnJheS5pc0FycmF5KGhlYWRsaW5lKSA/IGhlYWRsaW5lIDogW2hlYWRsaW5lXVxuXG4gIHJldHVybiAoXG4gICAgPGRpdiB7Li4ub3V0ZXJQcm9wc30gY2xhc3NOYW1lPXtjbignZmxleCBmbGV4LWNvbCcsIG91dGVyUHJvcHMuY2xhc3NOYW1lKX0+XG4gICAgICA8RGlzcGF0Y2hIZWFkZXIgY2hhbm5lbD17Y2hhbm5lbH0gLz5cblxuICAgICAgPGRpdlxuICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICdyZWxhdGl2ZSBtaW4taC0wIG1pbi13LTAgZmxleC0xJyxcbiAgICAgICAgICByZXNvbHZlZExheW91dCA9PT0gJ3NwbGl0J1xuICAgICAgICAgICAgPyAnZ3JpZCBncmlkLWNvbHMtWzNmcl8yZnJdJ1xuICAgICAgICAgICAgOiAnZ3JpZCBncmlkLXJvd3MtWzNmcl8yZnJdJ1xuICAgICAgICApfVxuICAgICAgPlxuICAgICAgICA8ZGl2XG4gICAgICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgICAgICdyZWxhdGl2ZSBvdmVyZmxvdy1oaWRkZW4gYm9yZGVyLWN1cnJlbnQvMjAnLFxuICAgICAgICAgICAgcmVzb2x2ZWRMYXlvdXQgPT09ICdzcGxpdCcgPyAnYm9yZGVyLXInIDogJ2JvcmRlci1iJ1xuICAgICAgICAgICl9XG4gICAgICAgICAgc3R5bGU9e3sgYmFja2dyb3VuZENvbG9yOiAndmFyKC0tYmFja2dyb3VuZCknIH19XG4gICAgICAgID5cbiAgICAgICAgICA8SW1hZ2VEaXN0b3J0aW9uXG4gICAgICAgICAgICBhdXRvUGxheT17YXV0b1BsYXl9XG4gICAgICAgICAgICBzcmM9e3NyY31cbiAgICAgICAgICAgIHRpbnQ9e3RpbnR9XG4gICAgICAgICAgICB0aW50U3RyZW5ndGg9e3RpbnRTdHJlbmd0aH1cbiAgICAgICAgICAvPlxuXG4gICAgICAgICAge2Nvcm5lck1hcmtzICYmIChcbiAgICAgICAgICAgIDw+XG4gICAgICAgICAgICAgIDxDb3JuZXJNYXJrIGNsYXNzTmFtZT1cInRvcC0zIGxlZnQtM1wiIC8+XG4gICAgICAgICAgICAgIDxDb3JuZXJNYXJrIGNsYXNzTmFtZT1cInRvcC0zIHJpZ2h0LTNcIiAvPlxuICAgICAgICAgICAgICA8Q29ybmVyTWFyayBjbGFzc05hbWU9XCJib3R0b20tMyBsZWZ0LTNcIiAvPlxuICAgICAgICAgICAgICA8Q29ybmVyTWFyayBjbGFzc05hbWU9XCJyaWdodC0zIGJvdHRvbS0zXCIgLz5cbiAgICAgICAgICAgIDwvPlxuICAgICAgICAgICl9XG5cbiAgICAgICAgICA8U2NhbmxpbmVPdmVybGF5IC8+XG5cbiAgICAgICAgICA8U21hbGwgY2xhc3NOYW1lPVwiYWJzb2x1dGUgYm90dG9tLTQgbGVmdC00IHotMSBvcGFjaXR5LTgwXCI+XG4gICAgICAgICAgICBIZXJtZXMgQWdlbnRcbiAgICAgICAgICA8L1NtYWxsPlxuICAgICAgICA8L2Rpdj5cblxuICAgICAgICA8YXNpZGUgY2xhc3NOYW1lPVwicmVsYXRpdmUgZmxleCBtaW4tdy0wIGZsZXgtY29sIGp1c3RpZnktYmV0d2VlbiBnYXAtOCBwLThcIj5cbiAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImZsZXggZmxleC1jb2wgZ2FwLTVcIj5cbiAgICAgICAgICAgIHtleWVicm93ICYmIChcbiAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGl0ZW1zLWNlbnRlciBnYXAtMlwiPlxuICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzTmFtZT1cImJnLW1pZGdyb3VuZC84MCBoLXB4IGZsZXgtMVwiIC8+XG5cbiAgICAgICAgICAgICAgICA8U21hbGwgY2xhc3NOYW1lPVwib3BhY2l0eS04MFwiPntleWVicm93fTwvU21hbGw+XG4gICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgKX1cblxuICAgICAgICAgICAge2NoaWxkcmVuID8/IChcbiAgICAgICAgICAgICAgPD5cbiAgICAgICAgICAgICAgICA8VHlwb2dyYXBoeVxuICAgICAgICAgICAgICAgICAgYXM9XCJoMVwiXG4gICAgICAgICAgICAgICAgICBjbGFzc05hbWU9XCJ0ZXh0LVsyLjc1ZW1dIGxlYWRpbmctWzAuOTVdIGZvbnQtYm9sZCB0cmFja2luZy1bLTAuMDFlbV1cIlxuICAgICAgICAgICAgICAgICAgZXhwYW5kZWRcbiAgICAgICAgICAgICAgICA+XG4gICAgICAgICAgICAgICAgICB7aGVhZGxpbmVMaW5lcy5tYXAoKGxpbmUsIGkpID0+IChcbiAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3NOYW1lPVwiYmxvY2tcIiBrZXk9e2Ake2xpbmV9LSR7aX1gfT5cbiAgICAgICAgICAgICAgICAgICAgICB7bGluZX1cbiAgICAgICAgICAgICAgICAgICAgPC9zcGFuPlxuICAgICAgICAgICAgICAgICAgKSl9XG4gICAgICAgICAgICAgICAgPC9UeXBvZ3JhcGh5PlxuXG4gICAgICAgICAgICAgICAge2JvZHkgJiYgKFxuICAgICAgICAgICAgICAgICAgPHAgY2xhc3NOYW1lPVwidGV4dC1bMS4wNjI1ZW1dIGxlYWRpbmctWzEuNV0gdHJhY2tpbmctbm9ybWFsIG5vcm1hbC1jYXNlIG9wYWNpdHktNjBcIj5cbiAgICAgICAgICAgICAgICAgICAge2JvZHl9XG4gICAgICAgICAgICAgICAgICA8L3A+XG4gICAgICAgICAgICAgICAgKX1cbiAgICAgICAgICAgICAgPC8+XG4gICAgICAgICAgICApfVxuICAgICAgICAgIDwvZGl2PlxuXG4gICAgICAgICAge3RhZ3MgJiYgdGFncy5sZW5ndGggPiAwICYmIChcbiAgICAgICAgICAgIDx1bCBjbGFzc05hbWU9XCJmbGV4IGZsZXgtY29sIGdhcC0yIGJvcmRlci10IGJvcmRlci1jdXJyZW50LzE1IHB0LTRcIj5cbiAgICAgICAgICAgICAge3RhZ3MubWFwKCh0YWcsIGkpID0+IChcbiAgICAgICAgICAgICAgICA8bGlcbiAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cImZsZXggaXRlbXMtYmFzZWxpbmUganVzdGlmeS1iZXR3ZWVuIGdhcC0zXCJcbiAgICAgICAgICAgICAgICAgIGtleT17YCR7dGFnfS0ke2l9YH1cbiAgICAgICAgICAgICAgICA+XG4gICAgICAgICAgICAgICAgICA8U21hbGwgY2xhc3NOYW1lPVwiZm9udC1jb3VyaWVyIG9wYWNpdHktNDBcIj5cbiAgICAgICAgICAgICAgICAgICAge1N0cmluZyhpICsgMSkucGFkU3RhcnQoMywgJzAnKX1cbiAgICAgICAgICAgICAgICAgIDwvU21hbGw+XG5cbiAgICAgICAgICAgICAgICAgIDxTbWFsbCBjbGFzc05hbWU9XCJvcGFjaXR5LTgwXCI+e3RhZ308L1NtYWxsPlxuXG4gICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzc05hbWU9XCJteC0xIGgtcHggZmxleC0xIHRyYW5zbGF0ZS15LVstM3B4XSBib3JkZXItYiBib3JkZXItZG90dGVkIGJvcmRlci1jdXJyZW50LzI1XCIgLz5cblxuICAgICAgICAgICAgICAgICAgPFNtYWxsIGNsYXNzTmFtZT1cImZvbnQtY291cmllciBvcGFjaXR5LTQwXCI+XG4gICAgICAgICAgICAgICAgICAgIHtTdHJpbmcoaSArIDEpLnBhZFN0YXJ0KDIsICcwJyl9L1xuICAgICAgICAgICAgICAgICAgICB7U3RyaW5nKHRhZ3MubGVuZ3RoKS5wYWRTdGFydCgyLCAnMCcpfVxuICAgICAgICAgICAgICAgICAgPC9TbWFsbD5cbiAgICAgICAgICAgICAgICA8L2xpPlxuICAgICAgICAgICAgICApKX1cbiAgICAgICAgICAgIDwvdWw+XG4gICAgICAgICAgKX1cbiAgICAgICAgPC9hc2lkZT5cbiAgICAgIDwvZGl2PlxuXG4gICAgICA8Zm9vdGVyIGNsYXNzTmFtZT1cImZsZXggaXRlbXMtY2VudGVyIGp1c3RpZnktYmV0d2VlbiBnYXAtNCBib3JkZXItdCBib3JkZXItY3VycmVudC8yMCBweC02IHB5LTNcIj5cbiAgICAgICAgPFNtYWxsIGNsYXNzTmFtZT1cIm9wYWNpdHktNzBcIj5cbiAgICAgICAgICB7c2lnbmF0dXJlfVxuXG4gICAgICAgICAgPEJsaW5rIC8+XG4gICAgICAgIDwvU21hbGw+XG5cbiAgICAgICAgPFNtYWxsIGNsYXNzTmFtZT1cImZvbnQtY291cmllciBvcGFjaXR5LTQwXCI+e3NlYWx9PC9TbWFsbD5cbiAgICAgIDwvZm9vdGVyPlxuICAgIDwvZGl2PlxuICApXG59XG5cbmZ1bmN0aW9uIERpc3BhdGNoSGVhZGVyKHsgY2hhbm5lbCB9OiB7IGNoYW5uZWw6IFJlYWN0LlJlYWN0Tm9kZSB9KSB7XG4gIGNvbnN0IGNsb2NrID0gdXNlVXRjQ2xvY2soKVxuXG4gIHJldHVybiAoXG4gICAgPGhlYWRlciBjbGFzc05hbWU9XCJmbGV4IGl0ZW1zLWNlbnRlciBqdXN0aWZ5LWJldHdlZW4gZ2FwLTQgYm9yZGVyLWIgYm9yZGVyLWN1cnJlbnQvMjAgcHgtNiBweS0zXCI+XG4gICAgICA8ZGl2IGNsYXNzTmFtZT1cImZsZXggaXRlbXMtY2VudGVyIGdhcC0zXCI+XG4gICAgICAgIDxzcGFuIGNsYXNzTmFtZT1cImJnLW1pZGdyb3VuZCBzaXplLTIgcm91bmRlZC1zbSBvcGFjaXR5LTcwXCIgLz5cblxuICAgICAgICA8U21hbGwgY2xhc3NOYW1lPVwib3BhY2l0eS03MFwiPntjaGFubmVsfTwvU21hbGw+XG4gICAgICA8L2Rpdj5cblxuICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGl0ZW1zLWNlbnRlciBnYXAtNFwiPlxuICAgICAgICA8Q2hhbm5lbERvdCAvPlxuXG4gICAgICAgIDxTbWFsbCBjbGFzc05hbWU9XCJmb250LWNvdXJpZXIgb3BhY2l0eS01MFwiPntjbG9ja30gVVRDPC9TbWFsbD5cbiAgICAgIDwvZGl2PlxuICAgIDwvaGVhZGVyPlxuICApXG59XG5cbmludGVyZmFjZSBWaWJlQ29udGVudFByb3BzIHtcbiAgYXV0b1BsYXk6IEF1dG9QbGF5UGF0dGVyblxuICBjaGFubmVsOiBSZWFjdC5SZWFjdE5vZGVcbiAgY29ybmVyTWFya3M6IGJvb2xlYW5cbiAgc2lnbmF0dXJlOiBSZWFjdC5SZWFjdE5vZGVcbiAgc3JjOiBzdHJpbmdcbiAgdGludD86IHN0cmluZ1xuICB0aW50U3RyZW5ndGg/OiB7IGFjdGl2ZTogbnVtYmVyOyBpbmFjdGl2ZTogbnVtYmVyIH1cbn1cblxuZnVuY3Rpb24gVmliZUNvbnRlbnQoe1xuICBhdXRvUGxheSxcbiAgY2hhbm5lbCxcbiAgY29ybmVyTWFya3MsXG4gIHNpZ25hdHVyZSxcbiAgc3JjLFxuICB0aW50LFxuICB0aW50U3RyZW5ndGhcbn06IFZpYmVDb250ZW50UHJvcHMpIHtcbiAgLy8gQWJzb2x1dGUtaW5zZXQtMCBndWFyYW50ZWVzIHRoaXMgZmlsbHMgdGhlIHBvc3RlciBldmVuIHdoZW4gdGhlIG91dGVyXG4gIC8vIGNvbnRhaW5lciB1c2VzIGFzcGVjdC1yYXRpby1kZXJpdmVkIGhlaWdodCBpbiBhIGJyb3dzZXIgdGhhdCBkb2Vzbid0XG4gIC8vIHByb3BhZ2F0ZSB0aGF0IGFzIGEgZGVmaW5pdGUgaGVpZ2h0IGZvciBwZXJjZW50YWdlLWJhc2VkIGNoaWxkcmVuLlxuICByZXR1cm4gKFxuICAgIDxkaXYgY2xhc3NOYW1lPVwiYWJzb2x1dGUgaW5zZXQtMFwiPlxuICAgICAgPEltYWdlRGlzdG9ydGlvblxuICAgICAgICBhdXRvUGxheT17YXV0b1BsYXl9XG4gICAgICAgIHNyYz17c3JjfVxuICAgICAgICB0aW50PXt0aW50fVxuICAgICAgICB0aW50U3RyZW5ndGg9e3RpbnRTdHJlbmd0aH1cbiAgICAgIC8+XG5cbiAgICAgIHtjb3JuZXJNYXJrcyAmJiAoXG4gICAgICAgIDw+XG4gICAgICAgICAgPENvcm5lck1hcmsgY2xhc3NOYW1lPVwidG9wLTUgbGVmdC01XCIgLz5cbiAgICAgICAgICA8Q29ybmVyTWFyayBjbGFzc05hbWU9XCJ0b3AtNSByaWdodC01XCIgLz5cbiAgICAgICAgICA8Q29ybmVyTWFyayBjbGFzc05hbWU9XCJib3R0b20tNSBsZWZ0LTVcIiAvPlxuICAgICAgICAgIDxDb3JuZXJNYXJrIGNsYXNzTmFtZT1cInJpZ2h0LTUgYm90dG9tLTVcIiAvPlxuICAgICAgICA8Lz5cbiAgICAgICl9XG5cbiAgICAgIDxTY2FubGluZU92ZXJsYXkgLz5cblxuICAgICAge2NoYW5uZWwgJiYgKFxuICAgICAgICA8U21hbGwgY2xhc3NOYW1lPVwiYWJzb2x1dGUgdG9wLTUgbGVmdC0xMCB6LTEgdGV4dC1bMC43NWVtXSBvcGFjaXR5LTcwXCI+XG4gICAgICAgICAge2NoYW5uZWx9XG4gICAgICAgIDwvU21hbGw+XG4gICAgICApfVxuXG4gICAgICA8U21hbGwgY2xhc3NOYW1lPVwiYWJzb2x1dGUgcmlnaHQtMTAgYm90dG9tLTUgei0xIHRleHQtWzAuNzVlbV0gb3BhY2l0eS04MFwiPlxuICAgICAgICB7c2lnbmF0dXJlfVxuICAgICAgPC9TbWFsbD5cbiAgICA8L2Rpdj5cbiAgKVxufVxuXG5leHBvcnQgdHlwZSBQb3N0ZXJBc3BlY3QgPVxuICB8ICdsYW5kc2NhcGUnXG4gIHwgJ3BvcnRyYWl0J1xuICB8ICdzcXVhcmUnXG4gIHwgJ3N0b3J5J1xuICB8ICd3aWRlJ1xuXG5leHBvcnQgdHlwZSBQb3N0ZXJWYXJpYW50ID0gJ2Rpc3BhdGNoJyB8ICd2aWJlJ1xuXG5leHBvcnQgaW50ZXJmYWNlIFBvc3RlclByb3BzIHtcbiAgLyoqIE91dHB1dCBhc3BlY3QgcmF0aW8uIFBpY2tzIHNlbnNpYmxlIGRlZmF1bHRzIGZvciBjb21tb24gc29jaWFsIGZvcm1hdHMuICovXG4gIGFzcGVjdD86IFBvc3RlckFzcGVjdFxuICAvKiogRGlzdG9ydGlvbiBjaG9yZW9ncmFwaHkgcGF0dGVybi4gRGVmYXVsdDogYCdzbGFzaCdgLiAqL1xuICBhdXRvUGxheT86IEF1dG9QbGF5UGF0dGVyblxuICAvKiogKGBkaXNwYXRjaGAgb25seSkgRGVzY3JpcHRpdmUgY29weSB1bmRlciB0aGUgaGVhZGxpbmUuICovXG4gIGJvZHk/OiBSZWFjdC5SZWFjdE5vZGVcbiAgLyoqIFNob3cgdGhlIHRoaW4gb3V0ZXIgZnJhbWUgYXJvdW5kIHRoZSBwb3N0ZXIuIERlZmF1bHQgYHRydWVgLiAqL1xuICBib3JkZXI/OiBib29sZWFuXG4gIC8qKiBUaW55IGJyb2FkY2FzdC1zdGF0aW9uIGxhYmVsLiBPcHRpb25hbCBpbiBgdmliZWA7IHNob3duIGluIGhlYWRlciBpbiBgZGlzcGF0Y2hgLiAqL1xuICBjaGFubmVsPzogUmVhY3QuUmVhY3ROb2RlXG4gIC8qKiAoYGRpc3BhdGNoYCBvbmx5KSBPdmVycmlkZSB0aGUgc2lkZWJhciBjb250ZW50ICh0YWtlcyBwcmVjZWRlbmNlIG92ZXIgaGVhZGxpbmUvYm9keSkuICovXG4gIGNoaWxkcmVuPzogUmVhY3QuUmVhY3ROb2RlXG4gIGNsYXNzTmFtZT86IHN0cmluZ1xuICAvKiogU2hvdyB0aGUgc21hbGwgYCtgIGRpZS1saW5lIHJlZ2lzdHJhdGlvbiBtYXJrcyBpbiB0aGUgaW1hZ2UgY29ybmVycy4gRGVmYXVsdCBgdHJ1ZWAuICovXG4gIGNvcm5lck1hcmtzPzogYm9vbGVhblxuICAvKiogKGBkaXNwYXRjaGAgb25seSkgU21hbGwgdGFnbGluZSBhYm92ZSB0aGUgaGVhZGxpbmUuICovXG4gIGV5ZWJyb3c/OiBSZWFjdC5SZWFjdE5vZGVcbiAgLyoqIChgZGlzcGF0Y2hgIG9ubHkpIEJpZyBleHBhbmRlZC10eXBvZ3JhcGh5IGhlYWRsaW5lLiBQYXNzIGFuIGFycmF5IG9mIHN0cmluZ3MgdG8gc3RhY2sgbGluZXMuICovXG4gIGhlYWRsaW5lPzogc3RyaW5nW10gfCBzdHJpbmdcbiAgLyoqIChgZGlzcGF0Y2hgIG9ubHkpIEZvcmNlIHN0YWNrZWQgdnMgc3BsaXQgbGF5b3V0LiBEZWZhdWx0IGluZmVycmVkIGZyb20gYGFzcGVjdGAuICovXG4gIGxheW91dD86ICdzcGxpdCcgfCAnc3RhY2tlZCdcbiAgLyoqIFJlbmRlciBzY2FsZS4gMSA9IGZ1bGwgY2FudmFzICgxMDgwcHgrIGJhc2Ugd2lkdGgpLiAqL1xuICBzY2FsZT86IG51bWJlclxuICAvKiogKGBkaXNwYXRjaGAgb25seSkgU21hbGwgbGVnYWwgLyBzaWduYXR1cmUgbGluZSBhdCB0aGUgYm90dG9tLXJpZ2h0LiAqL1xuICBzZWFsPzogUmVhY3QuUmVhY3ROb2RlXG4gIC8qKlxuICAgKiBTaWduYXR1cmUgbWFyay4gSW4gYHZpYmVgIHRoaXMgaXMgdGhlIHNtYWxsIFwiSGVybWVzIEFnZW50XCIgb3ZlcmxheSBpbiB0aGVcbiAgICogYm90dG9tLXJpZ2h0LiBJbiBgZGlzcGF0Y2hgIHRoaXMgaXMgdGhlIFVSTCAvIENUQSBpbiB0aGUgZm9vdGVyLlxuICAgKi9cbiAgc2lnbmF0dXJlPzogUmVhY3QuUmVhY3ROb2RlXG4gIC8qKiBPdmVycmlkZSB0aGUgcG9zdGVyIGltYWdlLiBEZWZhdWx0cyB0byB0aGUgSGVybWVzIFwiZmlsbGVyLWJnMFwiIGFzc2V0LiAqL1xuICBzcmM/OiBzdHJpbmdcbiAgLyoqIChgZGlzcGF0Y2hgIG9ubHkpIFJhbmtlZCBsaXN0IG9mIGZlYXR1cmVzIC8gcHJpY2luZyB0aWVycyByZW5kZXJlZCBhcyBhIG51bWJlcmVkIHNpZGViYXIgbGlzdC4gKi9cbiAgdGFncz86IHN0cmluZ1tdXG4gIC8qKiBTaGFkZXIgdGludCBvdmVybGF5LiBHcmVhdCBmb3IgdGllci1jb2xvcmVkIHZhcmlhbnRzLiAqL1xuICB0aW50Pzogc3RyaW5nXG4gIC8qKiBBY3RpdmUgLyBpbmFjdGl2ZSB0aW50IHN0cmVuZ3RoIFx1MjAxNCBkZWZhdWx0cyBtYXRjaCBgSW1hZ2VEaXN0b3J0aW9uYC4gKi9cbiAgdGludFN0cmVuZ3RoPzogeyBhY3RpdmU6IG51bWJlcjsgaW5hY3RpdmU6IG51bWJlciB9XG4gIC8qKiBMYXlvdXQgdmFyaWFudC4gYCd2aWJlJ2AgKGRlZmF1bHQpIGlzIGZ1bGwtYmxlZWQgaW1hZ2U7IGAnZGlzcGF0Y2gnYCBpcyB0aGUgYnJvYWRjYXN0LWNhcmQgd2l0aCBzaWRlYmFyIGNvcHkuICovXG4gIHZhcmlhbnQ/OiBQb3N0ZXJWYXJpYW50XG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBMkNJLFNBMkpRLFVBcEpOLEtBUEY7QUF6Q0osU0FBUyxXQUFXLGdCQUFnQjtBQUVwQyxPQUFPLGNBQWM7QUFDckIsU0FBUyxVQUFVO0FBRW5CLFNBQVMsYUFBYTtBQUN0QixTQUFTLHVCQUF1QjtBQUNoQyxTQUFTLGtCQUFrQjtBQUMzQixTQUFTLGFBQWE7QUFJdEIsTUFBTSxnQkFHRjtBQUFBLEVBQ0YsV0FBVyxFQUFFLGVBQWUsU0FBUyxRQUFRLE1BQU0sT0FBTyxLQUFLO0FBQUEsRUFDL0QsVUFBVSxFQUFFLGVBQWUsU0FBUyxRQUFRLE1BQU0sT0FBTyxLQUFLO0FBQUEsRUFDOUQsUUFBUSxFQUFFLGVBQWUsU0FBUyxRQUFRLE1BQU0sT0FBTyxLQUFLO0FBQUEsRUFDNUQsT0FBTyxFQUFFLGVBQWUsV0FBVyxRQUFRLE1BQU0sT0FBTyxLQUFLO0FBQUEsRUFDN0QsTUFBTSxFQUFFLGVBQWUsU0FBUyxRQUFRLEtBQUssT0FBTyxLQUFLO0FBQzNEO0FBRUEsTUFBTSxjQUNILFNBQThCLE9BQVE7QUFFekMsU0FBUyxjQUFjO0FBQ3JCLFFBQU0sQ0FBQyxLQUFLLE1BQU0sSUFBSSxTQUFzQixJQUFJO0FBRWhELFlBQVUsTUFBTTtBQUNkLFdBQU8sb0JBQUksS0FBSyxDQUFDO0FBQ2pCLFVBQU0sS0FBSyxZQUFZLE1BQU0sT0FBTyxvQkFBSSxLQUFLLENBQUMsR0FBRyxHQUFJO0FBRXJELFdBQU8sTUFBTSxjQUFjLEVBQUU7QUFBQSxF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
