"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "../../utils/index.js";
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
export function TerminalDemo({
  ariaLabel = "Terminal Demo",
  className,
  height = 320,
  label = "Terminal",
  loopDelayMs = 1e3,
  outputLineDelayMs = 50,
  sequence
}) {
  const bodyRef = useRef(null);
  const startedRef = useRef(false);
  const [html, setHtml] = useState("");
  const runDemo = useCallback(async () => {
    if (startedRef.current) {
      return;
    }
    startedRef.current = true;
    let content = "";
    const render = (h) => {
      content = h;
      setHtml(h);
    };
    for (; ; ) {
      for (const step of sequence) {
        switch (step.type) {
          case "clear":
            content = "";
            render("");
            break;
          case "output":
            for (const line of step.lines) {
              render(content + "\n" + line);
              await sleep(outputLineDelayMs);
            }
            break;
          case "pause":
            await sleep(step.ms);
            break;
          case "prompt":
            render(content + `<span class="text-midground">${step.text}</span>`);
            break;
          case "type":
            for (const char of step.text) {
              render(content + char);
              await sleep(step.delay ?? 30);
            }
            break;
        }
      }
      content = "";
      render("");
      await sleep(loopDelayMs);
    }
  }, [loopDelayMs, outputLineDelayMs, sequence]);
  useEffect(() => {
    const el = bodyRef.current?.closest("[data-demo-root]");
    if (!el) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            runDemo();
          }
        });
      },
      { threshold: 0.3 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [runDemo]);
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [html]);
  return /* @__PURE__ */ jsxs(
    "div",
    {
      "aria-label": ariaLabel,
      className: cn("border-4 border-double border-inherit", className),
      "data-demo-root": true,
      role: "img",
      children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3 border-b border-current/10 px-3 py-2", children: [
          /* @__PURE__ */ jsxs("div", { className: "flex gap-1.5", children: [
            /* @__PURE__ */ jsx(
              "span",
              {
                className: "bg-midground size-2 rounded-full",
                style: { mixBlendMode: "plus-lighter" }
              }
            ),
            /* @__PURE__ */ jsx("span", { className: "bg-midground/60 size-2 rounded-full" }),
            /* @__PURE__ */ jsx("span", { className: "bg-midground/30 size-2 rounded-full" })
          ] }),
          /* @__PURE__ */ jsx("span", { className: "font-courier text-display text-xs tracking-widest text-text-tertiary", children: label })
        ] }),
        /* @__PURE__ */ jsx(
          "div",
          {
            className: cn(
              "overflow-x-hidden overflow-y-auto whitespace-pre-wrap",
              "font-courier p-4 text-[0.75rem] leading-[1.7] normal-case"
            ),
            dangerouslySetInnerHTML: {
              __html: html + '<span class="blink inline-block dither ml-0.5 h-[1em] w-[1ch]"></span>'
            },
            ref: bodyRef,
            style: { height }
          }
        )
      ]
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZUNhbGxiYWNrLCB1c2VFZmZlY3QsIHVzZVJlZiwgdXNlU3RhdGUgfSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuZnVuY3Rpb24gc2xlZXAobXM6IG51bWJlcikge1xuICByZXR1cm4gbmV3IFByb21pc2U8dm9pZD4ocmVzb2x2ZSA9PiBzZXRUaW1lb3V0KHJlc29sdmUsIG1zKSlcbn1cblxuZXhwb3J0IGZ1bmN0aW9uIFRlcm1pbmFsRGVtbyh7XG4gIGFyaWFMYWJlbCA9ICdUZXJtaW5hbCBEZW1vJyxcbiAgY2xhc3NOYW1lLFxuICBoZWlnaHQgPSAzMjAsXG4gIGxhYmVsID0gJ1Rlcm1pbmFsJyxcbiAgbG9vcERlbGF5TXMgPSAxMDAwLFxuICBvdXRwdXRMaW5lRGVsYXlNcyA9IDUwLFxuICBzZXF1ZW5jZVxufTogVGVybWluYWxEZW1vUHJvcHMpIHtcbiAgY29uc3QgYm9keVJlZiA9IHVzZVJlZjxIVE1MRGl2RWxlbWVudD4obnVsbClcbiAgY29uc3Qgc3RhcnRlZFJlZiA9IHVzZVJlZihmYWxzZSlcbiAgY29uc3QgW2h0bWwsIHNldEh0bWxdID0gdXNlU3RhdGUoJycpXG5cbiAgY29uc3QgcnVuRGVtbyA9IHVzZUNhbGxiYWNrKGFzeW5jICgpID0+IHtcbiAgICBpZiAoc3RhcnRlZFJlZi5jdXJyZW50KSB7XG4gICAgICByZXR1cm5cbiAgICB9XG5cbiAgICBzdGFydGVkUmVmLmN1cnJlbnQgPSB0cnVlXG4gICAgbGV0IGNvbnRlbnQgPSAnJ1xuXG4gICAgY29uc3QgcmVuZGVyID0gKGg6IHN0cmluZykgPT4ge1xuICAgICAgY29udGVudCA9IGhcbiAgICAgIHNldEh0bWwoaClcbiAgICB9XG5cbiAgICBmb3IgKDs7KSB7XG4gICAgICBmb3IgKGNvbnN0IHN0ZXAgb2Ygc2VxdWVuY2UpIHtcbiAgICAgICAgc3dpdGNoIChzdGVwLnR5cGUpIHtcbiAgICAgICAgICBjYXNlICdjbGVhcic6XG4gICAgICAgICAgICBjb250ZW50ID0gJydcbiAgICAgICAgICAgIHJlbmRlcignJylcblxuICAgICAgICAgICAgYnJlYWtcblxuICAgICAgICAgIGNhc2UgJ291dHB1dCc6XG4gICAgICAgICAgICBmb3IgKGNvbnN0IGxpbmUgb2Ygc3RlcC5saW5lcykge1xuICAgICAgICAgICAgICByZW5kZXIoY29udGVudCArICdcXG4nICsgbGluZSlcbiAgICAgICAgICAgICAgYXdhaXQgc2xlZXAob3V0cHV0TGluZURlbGF5TXMpXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGJyZWFrXG5cbiAgICAgICAgICBjYXNlICdwYXVzZSc6XG4gICAgICAgICAgICBhd2FpdCBzbGVlcChzdGVwLm1zKVxuXG4gICAgICAgICAgICBicmVha1xuXG4gICAgICAgICAgY2FzZSAncHJvbXB0JzpcbiAgICAgICAgICAgIHJlbmRlcihjb250ZW50ICsgYDxzcGFuIGNsYXNzPVwidGV4dC1taWRncm91bmRcIj4ke3N0ZXAudGV4dH08L3NwYW4+YClcblxuICAgICAgICAgICAgYnJlYWtcblxuICAgICAgICAgIGNhc2UgJ3R5cGUnOlxuICAgICAgICAgICAgZm9yIChjb25zdCBjaGFyIG9mIHN0ZXAudGV4dCkge1xuICAgICAgICAgICAgICByZW5kZXIoY29udGVudCArIGNoYXIpXG4gICAgICAgICAgICAgIGF3YWl0IHNsZWVwKHN0ZXAuZGVsYXkgPz8gMzApXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGJyZWFrXG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgY29udGVudCA9ICcnXG4gICAgICByZW5kZXIoJycpXG4gICAgICBhd2FpdCBzbGVlcChsb29wRGVsYXlNcylcbiAgICB9XG4gIH0sIFtsb29wRGVsYXlNcywgb3V0cHV0TGluZURlbGF5TXMsIHNlcXVlbmNlXSlcblxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIGNvbnN0IGVsID0gYm9keVJlZi5jdXJyZW50Py5jbG9zZXN0KCdbZGF0YS1kZW1vLXJvb3RdJylcblxuICAgIGlmICghZWwpIHtcbiAgICAgIHJldHVyblxuICAgIH1cblxuICAgIGNvbnN0IG9ic2VydmVyID0gbmV3IEludGVyc2VjdGlvbk9ic2VydmVyKFxuICAgICAgZW50cmllcyA9PiB7XG4gICAgICAgIGVudHJpZXMuZm9yRWFjaChlbnRyeSA9PiB7XG4gICAgICAgICAgaWYgKGVudHJ5LmlzSW50ZXJzZWN0aW5nKSB7XG4gICAgICAgICAgICBydW5EZW1vKClcbiAgICAgICAgICB9XG4gICAgICAgIH0pXG4gICAgICB9LFxuICAgICAgeyB0aHJlc2hvbGQ6IDAuMyB9XG4gICAgKVxuXG4gICAgb2JzZXJ2ZXIub2JzZXJ2ZShlbClcblxuICAgIHJldHVybiAoKSA9PiBvYnNlcnZlci5kaXNjb25uZWN0KClcbiAgfSwgW3J1bkRlbW9dKVxuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgaWYgKGJvZHlSZWYuY3VycmVudCkge1xuICAgICAgYm9keVJlZi5jdXJyZW50LnNjcm9sbFRvcCA9IGJvZHlSZWYuY3VycmVudC5zY3JvbGxIZWlnaHRcbiAgICB9XG4gIH0sIFtodG1sXSlcblxuICByZXR1cm4gKFxuICAgIDxkaXZcbiAgICAgIGFyaWEtbGFiZWw9e2FyaWFMYWJlbH1cbiAgICAgIGNsYXNzTmFtZT17Y24oJ2JvcmRlci00IGJvcmRlci1kb3VibGUgYm9yZGVyLWluaGVyaXQnLCBjbGFzc05hbWUpfVxuICAgICAgZGF0YS1kZW1vLXJvb3RcbiAgICAgIHJvbGU9XCJpbWdcIlxuICAgID5cbiAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBpdGVtcy1jZW50ZXIgZ2FwLTMgYm9yZGVyLWIgYm9yZGVyLWN1cnJlbnQvMTAgcHgtMyBweS0yXCI+XG4gICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBnYXAtMS41XCI+XG4gICAgICAgICAgPHNwYW5cbiAgICAgICAgICAgIGNsYXNzTmFtZT1cImJnLW1pZGdyb3VuZCBzaXplLTIgcm91bmRlZC1mdWxsXCJcbiAgICAgICAgICAgIHN0eWxlPXt7IG1peEJsZW5kTW9kZTogJ3BsdXMtbGlnaHRlcicgfX1cbiAgICAgICAgICAvPlxuXG4gICAgICAgICAgPHNwYW4gY2xhc3NOYW1lPVwiYmctbWlkZ3JvdW5kLzYwIHNpemUtMiByb3VuZGVkLWZ1bGxcIiAvPlxuICAgICAgICAgIDxzcGFuIGNsYXNzTmFtZT1cImJnLW1pZGdyb3VuZC8zMCBzaXplLTIgcm91bmRlZC1mdWxsXCIgLz5cbiAgICAgICAgPC9kaXY+XG5cbiAgICAgICAgPHNwYW4gY2xhc3NOYW1lPVwiZm9udC1jb3VyaWVyIHRleHQtZGlzcGxheSB0ZXh0LXhzIHRyYWNraW5nLXdpZGVzdCB0ZXh0LXRleHQtdGVydGlhcnlcIj5cbiAgICAgICAgICB7bGFiZWx9XG4gICAgICAgIDwvc3Bhbj5cbiAgICAgIDwvZGl2PlxuXG4gICAgICA8ZGl2XG4gICAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICAgJ292ZXJmbG93LXgtaGlkZGVuIG92ZXJmbG93LXktYXV0byB3aGl0ZXNwYWNlLXByZS13cmFwJyxcbiAgICAgICAgICAnZm9udC1jb3VyaWVyIHAtNCB0ZXh0LVswLjc1cmVtXSBsZWFkaW5nLVsxLjddIG5vcm1hbC1jYXNlJ1xuICAgICAgICApfVxuICAgICAgICBkYW5nZXJvdXNseVNldElubmVySFRNTD17e1xuICAgICAgICAgIF9faHRtbDpcbiAgICAgICAgICAgIGh0bWwgK1xuICAgICAgICAgICAgJzxzcGFuIGNsYXNzPVwiYmxpbmsgaW5saW5lLWJsb2NrIGRpdGhlciBtbC0wLjUgaC1bMWVtXSB3LVsxY2hdXCI+PC9zcGFuPidcbiAgICAgICAgfX1cbiAgICAgICAgcmVmPXtib2R5UmVmfVxuICAgICAgICBzdHlsZT17eyBoZWlnaHQgfX1cbiAgICAgIC8+XG4gICAgPC9kaXY+XG4gIClcbn1cblxuaW50ZXJmYWNlIENsZWFyU3RlcCB7XG4gIHR5cGU6ICdjbGVhcidcbn1cblxuaW50ZXJmYWNlIE91dHB1dFN0ZXAge1xuICBsaW5lczogc3RyaW5nW11cbiAgdHlwZTogJ291dHB1dCdcbn1cblxuaW50ZXJmYWNlIFBhdXNlU3RlcCB7XG4gIG1zOiBudW1iZXJcbiAgdHlwZTogJ3BhdXNlJ1xufVxuXG5pbnRlcmZhY2UgUHJvbXB0U3RlcCB7XG4gIHRleHQ6IHN0cmluZ1xuICB0eXBlOiAncHJvbXB0J1xufVxuXG5pbnRlcmZhY2UgVGVybWluYWxEZW1vUHJvcHMge1xuICBhcmlhTGFiZWw/OiBzdHJpbmdcbiAgY2xhc3NOYW1lPzogc3RyaW5nXG4gIGhlaWdodD86IG51bWJlciB8IHN0cmluZ1xuICBsYWJlbD86IHN0cmluZ1xuICBsb29wRGVsYXlNcz86IG51bWJlclxuICBvdXRwdXRMaW5lRGVsYXlNcz86IG51bWJlclxuICBzZXF1ZW5jZTogVGVybWluYWxEZW1vU3RlcFtdXG59XG5cbmV4cG9ydCB0eXBlIFRlcm1pbmFsRGVtb1N0ZXAgPVxuICB8IENsZWFyU3RlcFxuICB8IE91dHB1dFN0ZXBcbiAgfCBQYXVzZVN0ZXBcbiAgfCBQcm9tcHRTdGVwXG4gIHwgVHlwZVN0ZXBcblxuaW50ZXJmYWNlIFR5cGVTdGVwIHtcbiAgZGVsYXk/OiBudW1iZXJcbiAgdGV4dDogc3RyaW5nXG4gIHR5cGU6ICd0eXBlJ1xufVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQW9IUSxTQUNFLEtBREY7QUFsSFIsU0FBUyxhQUFhLFdBQVcsUUFBUSxnQkFBZ0I7QUFFekQsU0FBUyxVQUFVO0FBRW5CLFNBQVMsTUFBTSxJQUFZO0FBQ3pCLFNBQU8sSUFBSSxRQUFjLGFBQVcsV0FBVyxTQUFTLEVBQUUsQ0FBQztBQUM3RDtBQUVPLGdCQUFTLGFBQWE7QUFBQSxFQUMzQixZQUFZO0FBQUEsRUFDWjtBQUFBLEVBQ0EsU0FBUztBQUFBLEVBQ1QsUUFBUTtBQUFBLEVBQ1IsY0FBYztBQUFBLEVBQ2Qsb0JBQW9CO0FBQUEsRUFDcEI7QUFDRixHQUFzQjtBQUNwQixR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
