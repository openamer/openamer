"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import {
  useEffect,
  useRef,
  useState
} from "react";
import { createPortal } from "react-dom";
import { cn } from "../../utils/index.js";
import { Typography } from "./typography/index.js";
const CLOSE_DRAG_MIN_PX = 72;
const CLOSE_DRAG_RATIO = 0.18;
const SHEET_TRANSITION_MS = 280;
export function BottomSheet({
  backdropDismissLabel = "Dismiss",
  children,
  onClose,
  open,
  title
}) {
  const [renderPortal, setRenderPortal] = useState(open);
  const [entered, setEntered] = useState(false);
  const [dragOffsetPx, setDragOffsetPx] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const closeTimerRef = useRef(null);
  const sheetRef = useRef(null);
  const dragTrackingRef = useRef(false);
  const dragStartYRef = useRef(0);
  const dragOffsetRef = useRef(0);
  const reducedMotion = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const syncDragPx = (next) => {
    dragOffsetRef.current = next;
    setDragOffsetPx(next);
  };
  useEffect(() => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    const ms = reducedMotion ? 0 : SHEET_TRANSITION_MS;
    let openRafId = 0;
    let exitRafId = 0;
    if (open) {
      openRafId = requestAnimationFrame(() => {
        dragTrackingRef.current = false;
        dragOffsetRef.current = 0;
        setDragActive(false);
        setDragOffsetPx(0);
        setRenderPortal(true);
        requestAnimationFrame(() => {
          requestAnimationFrame(() => setEntered(true));
        });
      });
    } else {
      exitRafId = requestAnimationFrame(() => {
        dragTrackingRef.current = false;
        setDragActive(false);
        setEntered(false);
        closeTimerRef.current = window.setTimeout(() => {
          dragOffsetRef.current = 0;
          setDragOffsetPx(0);
          setRenderPortal(false);
          closeTimerRef.current = null;
        }, ms);
      });
    }
    return () => {
      cancelAnimationFrame(openRafId);
      cancelAnimationFrame(exitRafId);
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
        closeTimerRef.current = null;
      }
    };
  }, [open, reducedMotion]);
  useEffect(() => {
    if (!renderPortal) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [renderPortal]);
  if (!renderPortal || typeof document === "undefined") return null;
  const durationClass = reducedMotion ? "duration-0" : "duration-[280ms]";
  const draggingVisual = dragActive || dragOffsetPx > 0;
  const onDragPointerDown = (e) => {
    if (reducedMotion || !entered) return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    dragTrackingRef.current = true;
    setDragActive(true);
    dragStartYRef.current = e.clientY;
    syncDragPx(0);
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onDragPointerMove = (e) => {
    if (!dragTrackingRef.current) return;
    const dy = e.clientY - dragStartYRef.current;
    const next = Math.max(0, dy);
    const sheetH = sheetRef.current?.offsetHeight ?? 560;
    syncDragPx(Math.min(next, sheetH));
  };
  const endDrag = (e) => {
    if (!dragTrackingRef.current) return;
    dragTrackingRef.current = false;
    setDragActive(false);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
    }
    const sheetH = sheetRef.current?.offsetHeight ?? 560;
    const threshold = Math.max(CLOSE_DRAG_MIN_PX, sheetH * CLOSE_DRAG_RATIO);
    const d = dragOffsetRef.current;
    if (d >= threshold) {
      onClose();
      return;
    }
    syncDragPx(0);
  };
  return createPortal(
    /* @__PURE__ */ jsxs("div", { className: "fixed inset-0 z-[200] flex flex-col justify-end", children: [
      /* @__PURE__ */ jsx(
        "button",
        {
          "aria-label": backdropDismissLabel,
          className: cn(
            "absolute inset-0 bg-black/55 backdrop-blur-[2px]",
            "transition-opacity ease-out motion-reduce:transition-none",
            durationClass,
            entered ? "opacity-100" : "opacity-0"
          ),
          onClick: onClose,
          type: "button"
        }
      ),
      /* @__PURE__ */ jsxs(
        "div",
        {
          "aria-label": title,
          "aria-modal": "true",
          className: cn(
            "relative flex max-h-[85dvh] min-h-0 flex-col rounded-t-xl border border-current/20",
            "bg-background-base/98 pb-[max(1rem,env(safe-area-inset-bottom))]",
            "shadow-[0_-12px_40px_-8px_rgba(0,0,0,0.55)] backdrop-blur-md",
            "ease-out motion-reduce:transition-none transform-gpu",
            draggingVisual ? "transition-none" : cn("transition-transform", durationClass),
            entered ? "translate-y-0" : "translate-y-full"
          ),
          ref: sheetRef,
          role: "dialog",
          style: entered && dragOffsetPx > 0 ? { transform: `translateY(${dragOffsetPx}px)` } : void 0,
          children: [
            /* @__PURE__ */ jsxs(
              "div",
              {
                className: cn(
                  "flex shrink-0 flex-col gap-2 border-b border-current/15 px-4 pb-3 pt-2",
                  "touch-none select-none",
                  reducedMotion ? "cursor-default" : "cursor-grab active:cursor-grabbing"
                ),
                onPointerCancel: endDrag,
                onPointerDown: onDragPointerDown,
                onPointerMove: onDragPointerMove,
                onPointerUp: endDrag,
                children: [
                  /* @__PURE__ */ jsx(
                    "div",
                    {
                      "aria-hidden": true,
                      className: "mx-auto h-1 w-10 shrink-0 rounded-full bg-current/20"
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    Typography,
                    {
                      className: "text-[0.65rem] tracking-[0.15em] uppercase text-midground/70",
                      mondwest: true,
                      children: title
                    }
                  )
                ]
              }
            ),
            /* @__PURE__ */ jsx("div", { className: "min-h-0 flex-1 overflow-y-auto overscroll-contain", children })
          ]
        }
      )
    ] }),
    document.body
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7XG4gIHR5cGUgUG9pbnRlckV2ZW50IGFzIFJlYWN0UG9pbnRlckV2ZW50LFxuICB0eXBlIFJlYWN0Tm9kZSxcbiAgdXNlRWZmZWN0LFxuICB1c2VSZWYsXG4gIHVzZVN0YXRlXG59IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHsgY3JlYXRlUG9ydGFsIH0gZnJvbSAncmVhY3QtZG9tJ1xuXG5pbXBvcnQgeyBjbiB9IGZyb20gJy4uLy4uL3V0aWxzJ1xuaW1wb3J0IHsgVHlwb2dyYXBoeSB9IGZyb20gJy4vdHlwb2dyYXBoeSdcblxuY29uc3QgQ0xPU0VfRFJBR19NSU5fUFggPSA3MlxuY29uc3QgQ0xPU0VfRFJBR19SQVRJTyA9IDAuMThcbmNvbnN0IFNIRUVUX1RSQU5TSVRJT05fTVMgPSAyODBcblxuLyoqXG4gKiBNb2JpbGUtZmlyc3QgYm90dG9tIHNoZWV0IHdpdGggc2xpZGUgKyBmYWRlIGVudGVyL2V4aXQsIGRyYWctdG8tZGlzbWlzc1xuICogaGFuZGxlLCBib2R5IHNjcm9sbCBsb2NrLCBhbmQgcmVkdWNlZC1tb3Rpb24gc3VwcG9ydC4gUG9ydGFsZWQgdG9cbiAqIGBkb2N1bWVudC5ib2R5YCB0byBlc2NhcGUgYW5jZXN0b3Igc3RhY2tpbmcgY29udGV4dHMuXG4gKi9cbmV4cG9ydCBmdW5jdGlvbiBCb3R0b21TaGVldCh7XG4gIGJhY2tkcm9wRGlzbWlzc0xhYmVsID0gJ0Rpc21pc3MnLFxuICBjaGlsZHJlbixcbiAgb25DbG9zZSxcbiAgb3BlbixcbiAgdGl0bGVcbn06IEJvdHRvbVNoZWV0UHJvcHMpIHtcbiAgY29uc3QgW3JlbmRlclBvcnRhbCwgc2V0UmVuZGVyUG9ydGFsXSA9IHVzZVN0YXRlKG9wZW4pXG4gIGNvbnN0IFtlbnRlcmVkLCBzZXRFbnRlcmVkXSA9IHVzZVN0YXRlKGZhbHNlKVxuICBjb25zdCBbZHJhZ09mZnNldFB4LCBzZXREcmFnT2Zmc2V0UHhdID0gdXNlU3RhdGUoMClcbiAgY29uc3QgW2RyYWdBY3RpdmUsIHNldERyYWdBY3RpdmVdID0gdXNlU3RhdGUoZmFsc2UpXG5cbiAgY29uc3QgY2xvc2VUaW1lclJlZiA9IHVzZVJlZjxSZXR1cm5UeXBlPHR5cGVvZiBzZXRUaW1lb3V0PiB8IG51bGw+KG51bGwpXG4gIGNvbnN0IHNoZWV0UmVmID0gdXNlUmVmPEhUTUxEaXZFbGVtZW50PihudWxsKVxuICBjb25zdCBkcmFnVHJhY2tpbmdSZWYgPSB1c2VSZWYoZmFsc2UpXG4gIGNvbnN0IGRyYWdTdGFydFlSZWYgPSB1c2VSZWYoMClcbiAgY29uc3QgZHJhZ09mZnNldFJlZiA9IHVzZVJlZigwKVxuXG4gIGNvbnN0IHJlZHVjZWRNb3Rpb24gPVxuICAgIHR5cGVvZiB3aW5kb3cgIT09ICd1bmRlZmluZWQnICYmXG4gICAgd2luZG93Lm1hdGNoTWVkaWEoJyhwcmVmZXJzLXJlZHVjZWQtbW90aW9uOiByZWR1Y2UpJykubWF0Y2hlc1xuXG4gIGNvbnN0IHN5bmNEcmFnUHggPSAobmV4dDogbnVtYmVyKSA9PiB7XG4gICAgZHJhZ09mZnNldFJlZi5jdXJyZW50ID0gbmV4dFxuICAgIHNldERyYWdPZmZzZXRQeChuZXh0KVxuICB9XG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBpZiAoY2xvc2VUaW1lclJlZi5jdXJyZW50KSB7XG4gICAgICBjbGVhclRpbWVvdXQoY2xvc2VUaW1lclJlZi5jdXJyZW50KVxuICAgICAgY2xvc2VUaW1lclJlZi5jdXJyZW50ID0gbnVsbFxuICAgIH1cblxuICAgIGNvbnN0IG1zID0gcmVkdWNlZE1vdGlvbiA/IDAgOiBTSEVFVF9UUkFOU0lUSU9OX01TXG5cbiAgICBsZXQgb3BlblJhZklkID0gMFxuICAgIGxldCBleGl0UmFmSWQgPSAwXG5cbiAgICBpZiAob3Blbikge1xuICAgICAgb3BlblJhZklkID0gcmVxdWVzdEFuaW1hdGlvbkZyYW1lKCgpID0+IHtcbiAgICAgICAgZHJhZ1RyYWNraW5nUmVmLmN1cnJlbnQgPSBmYWxzZVxuICAgICAgICBkcmFnT2Zmc2V0UmVmLmN1cnJlbnQgPSAwXG4gICAgICAgIHNldERyYWdBY3RpdmUoZmFsc2UpXG4gICAgICAgIHNldERyYWdPZmZzZXRQeCgwKVxuICAgICAgICBzZXRSZW5kZXJQb3J0YWwodHJ1ZSlcbiAgICAgICAgcmVxdWVzdEFuaW1hdGlvbkZyYW1lKCgpID0+IHtcbiAgICAgICAgICByZXF1ZXN0QW5pbWF0aW9uRnJhbWUoKCkgPT4gc2V0RW50ZXJlZCh0cnVlKSlcbiAgICAgICAgfSlcbiAgICAgIH0pXG4gICAgfSBlbHNlIHtcbiAgICAgIGV4aXRSYWZJZCA9IHJlcXVlc3RBbmltYXRpb25GcmFtZSgoKSA9PiB7XG4gICAgICAgIGRyYWdUcmFja2luZ1JlZi5jdXJyZW50ID0gZmFsc2VcbiAgICAgICAgc2V0RHJhZ0FjdGl2ZShmYWxzZSlcbiAgICAgICAgc2V0RW50ZXJlZChmYWxzZSlcbiAgICAgICAgY2xvc2VUaW1lclJlZi5jdXJyZW50ID0gd2luZG93LnNldFRpbWVvdXQoKCkgPT4ge1xuICAgICAgICAgIGRyYWdPZmZzZXRSZWYuY3VycmVudCA9IDBcbiAgICAgICAgICBzZXREcmFnT2Zmc2V0UHgoMClcbiAgICAgICAgICBzZXRSZW5kZXJQb3J0YWwoZmFsc2UpXG4gICAgICAgICAgY2xvc2VUaW1lclJlZi5jdXJyZW50ID0gbnVsbFxuICAgICAgICB9LCBtcylcbiAgICAgIH0pXG4gICAgfVxuXG4gICAgcmV0dXJuICgpID0+IHtcbiAgICAgIGNhbmNlbEFuaW1hdGlvbkZyYW1lKG9wZW5SYWZJZClcbiAgICAgIGNhbmNlbEFuaW1hdGlvbkZyYW1lKGV4aXRSYWZJZClcbiAgICAgIGlmIChjbG9zZVRpbWVyUmVmLmN1cnJlbnQpIHtcbiAgICAgICAgY2xlYXJUaW1lb3V0KGNsb3NlVGltZXJSZWYuY3VycmVudClcbiAgICAgICAgY2xvc2VUaW1lclJlZi5jdXJyZW50ID0gbnVsbFxuICAgICAgfVxuICAgIH1cbiAgfSwgW29wZW4sIHJlZHVjZWRNb3Rpb25dKVxuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgaWYgKCFyZW5kZXJQb3J0YWwpIHJldHVyblxuICAgIGNvbnN0IHByZXYgPSBkb2N1bWVudC5ib2R5LnN0eWxlLm92ZXJmbG93XG4gICAgZG9jdW1lbnQuYm9keS5zdHlsZS5vdmVyZmxvdyA9ICdoaWRkZW4nXG4gICAgcmV0dXJuICgpID0+IHtcbiAgICAgIGRvY3VtZW50LmJvZHkuc3R5bGUub3ZlcmZsb3cgPSBwcmV2XG4gICAgfVxuICB9LCBbcmVuZGVyUG9ydGFsXSlcblxuICBpZiAoIXJlbmRlclBvcnRhbCB8fCB0eXBlb2YgZG9jdW1lbnQgPT09ICd1bmRlZmluZWQnKSByZXR1cm4gbnVsbFxuXG4gIGNvbnN0IGR1cmF0aW9uQ2xhc3MgPSByZWR1Y2VkTW90aW9uID8gJ2R1cmF0aW9uLTAnIDogJ2R1cmF0aW9uLVsyODBtc10nXG4gIGNvbnN0IGRyYWdnaW5nVmlzdWFsID0gZHJhZ0FjdGl2ZSB8fCBkcmFnT2Zmc2V0UHggPiAwXG5cbiAgY29uc3Qgb25EcmFnUG9pbnRlckRvd24gPSAoZTogUmVhY3RQb2ludGVyRXZlbnQ8SFRNTERpdkVsZW1lbnQ+KSA9PiB7XG4gICAgaWYgKHJlZHVjZWRNb3Rpb24gfHwgIWVudGVyZWQpIHJldHVyblxuICAgIGlmIChlLnBvaW50ZXJUeXBlID09PSAnbW91c2UnICYmIGUuYnV0dG9uICE9PSAwKSByZXR1cm5cblxuICAgIGRyYWdUcmFja2luZ1JlZi5jdXJyZW50ID0gdHJ1ZVxuICAgIHNldERyYWdBY3RpdmUodHJ1ZSlcbiAgICBkcmFnU3RhcnRZUmVmLmN1cnJlbnQgPSBlLmNsaWVudFlcbiAgICBzeW5jRHJhZ1B4KDApXG4gICAgZS5jdXJyZW50VGFyZ2V0LnNldFBvaW50ZXJDYXB0dXJlKGUucG9pbnRlcklkKVxuICB9XG5cbiAgY29uc3Qgb25EcmFnUG9pbnRlck1vdmUgPSAoZTogUmVhY3RQb2ludGVyRXZlbnQ8SFRNTERpdkVsZW1lbnQ+KSA9PiB7XG4gICAgaWYgKCFkcmFnVHJhY2tpbmdSZWYuY3VycmVudCkgcmV0dXJuXG4gICAgY29uc3QgZHkgPSBlLmNsaWVudFkgLSBkcmFnU3RhcnRZUmVmLmN1cnJlbnRcbiAgICBjb25zdCBuZXh0ID0gTWF0aC5tYXgoMCwgZHkpXG4gICAgY29uc3Qgc2hlZXRIID0gc2hlZXRSZWYuY3VycmVudD8ub2Zmc2V0SGVpZ2h0ID8/IDU2MFxuICAgIHN5bmNEcmFnUHgoTWF0aC5taW4obmV4dCwgc2hlZXRIKSlcbiAgfVxuXG4gIGNvbnN0IGVuZERyYWcgPSAoZTogUmVhY3RQb2ludGVyRXZlbnQ8SFRNTERpdkVsZW1lbnQ+KSA9PiB7XG4gICAgaWYgKCFkcmFnVHJhY2tpbmdSZWYuY3VycmVudCkgcmV0dXJuXG4gICAgZHJhZ1RyYWNraW5nUmVmLmN1cnJlbnQgPSBmYWxzZVxuICAgIHNldERyYWdBY3RpdmUoZmFsc2UpXG4gICAgdHJ5IHtcbiAgICAgIGUuY3VycmVudFRhcmdldC5yZWxlYXNlUG9pbnRlckNhcHR1cmUoZS5wb2ludGVySWQpXG4gICAgfSBjYXRjaCB7XG4gICAgICAvKiBhbHJlYWR5IHJlbGVhc2VkICovXG4gICAgfVxuXG4gICAgY29uc3Qgc2hlZXRIID0gc2hlZXRSZWYuY3VycmVudD8ub2Zmc2V0SGVpZ2h0ID8/IDU2MFxuICAgIGNvbnN0IHRocmVzaG9sZCA9IE1hdGgubWF4KENMT1NFX0RSQUdfTUlOX1BYLCBzaGVldEggKiBDTE9TRV9EUkFHX1JBVElPKVxuICAgIGNvbnN0IGQgPSBkcmFnT2Zmc2V0UmVmLmN1cnJlbnRcblxuICAgIGlmIChkID49IHRocmVzaG9sZCkge1xuICAgICAgb25DbG9zZSgpXG4gICAgICByZXR1cm5cbiAgICB9XG4gICAgc3luY0RyYWdQeCgwKVxuICB9XG5cbiAgcmV0dXJuIGNyZWF0ZVBvcnRhbChcbiAgICA8ZGl2IGNsYXNzTmFtZT1cImZpeGVkIGluc2V0LTAgei1bMjAwXSBmbGV4IGZsZXgtY29sIGp1c3RpZnktZW5kXCI+XG4gICAgICA8YnV0dG9uXG4gICAgICAgIGFyaWEtbGFiZWw9e2JhY2tkcm9wRGlzbWlzc0xhYmVsfVxuICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICdhYnNvbHV0ZSBpbnNldC0wIGJnLWJsYWNrLzU1IGJhY2tkcm9wLWJsdXItWzJweF0nLFxuICAgICAgICAgICd0cmFuc2l0aW9uLW9wYWNpdHkgZWFzZS1vdXQgbW90aW9uLXJlZHVjZTp0cmFuc2l0aW9uLW5vbmUnLFxuICAgICAgICAgIGR1cmF0aW9uQ2xhc3MsXG4gICAgICAgICAgZW50ZXJlZCA/ICdvcGFjaXR5LTEwMCcgOiAnb3BhY2l0eS0wJ1xuICAgICAgICApfVxuICAgICAgICBvbkNsaWNrPXtvbkNsb3NlfVxuICAgICAgICB0eXBlPVwiYnV0dG9uXCJcbiAgICAgIC8+XG5cbiAgICAgIDxkaXZcbiAgICAgICAgYXJpYS1sYWJlbD17dGl0bGV9XG4gICAgICAgIGFyaWEtbW9kYWw9XCJ0cnVlXCJcbiAgICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgICAncmVsYXRpdmUgZmxleCBtYXgtaC1bODVkdmhdIG1pbi1oLTAgZmxleC1jb2wgcm91bmRlZC10LXhsIGJvcmRlciBib3JkZXItY3VycmVudC8yMCcsXG4gICAgICAgICAgJ2JnLWJhY2tncm91bmQtYmFzZS85OCBwYi1bbWF4KDFyZW0sZW52KHNhZmUtYXJlYS1pbnNldC1ib3R0b20pKV0nLFxuICAgICAgICAgICdzaGFkb3ctWzBfLTEycHhfNDBweF8tOHB4X3JnYmEoMCwwLDAsMC41NSldIGJhY2tkcm9wLWJsdXItbWQnLFxuICAgICAgICAgICdlYXNlLW91dCBtb3Rpb24tcmVkdWNlOnRyYW5zaXRpb24tbm9uZSB0cmFuc2Zvcm0tZ3B1JyxcbiAgICAgICAgICBkcmFnZ2luZ1Zpc3VhbFxuICAgICAgICAgICAgPyAndHJhbnNpdGlvbi1ub25lJ1xuICAgICAgICAgICAgOiBjbigndHJhbnNpdGlvbi10cmFuc2Zvcm0nLCBkdXJhdGlvbkNsYXNzKSxcbiAgICAgICAgICBlbnRlcmVkID8gJ3RyYW5zbGF0ZS15LTAnIDogJ3RyYW5zbGF0ZS15LWZ1bGwnXG4gICAgICAgICl9XG4gICAgICAgIHJlZj17c2hlZXRSZWZ9XG4gICAgICAgIHJvbGU9XCJkaWFsb2dcIlxuICAgICAgICBzdHlsZT17XG4gICAgICAgICAgZW50ZXJlZCAmJiBkcmFnT2Zmc2V0UHggPiAwXG4gICAgICAgICAgICA/IHsgdHJhbnNmb3JtOiBgdHJhbnNsYXRlWSgke2RyYWdPZmZzZXRQeH1weClgIH1cbiAgICAgICAgICAgIDogdW5kZWZpbmVkXG4gICAgICAgIH1cbiAgICAgID5cbiAgICAgICAgPGRpdlxuICAgICAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICAgICAnZmxleCBzaHJpbmstMCBmbGV4LWNvbCBnYXAtMiBib3JkZXItYiBib3JkZXItY3VycmVudC8xNSBweC00IHBiLTMgcHQtMicsXG4gICAgICAgICAgICAndG91Y2gtbm9uZSBzZWxlY3Qtbm9uZScsXG4gICAgICAgICAgICByZWR1Y2VkTW90aW9uXG4gICAgICAgICAgICAgID8gJ2N1cnNvci1kZWZhdWx0J1xuICAgICAgICAgICAgICA6ICdjdXJzb3ItZ3JhYiBhY3RpdmU6Y3Vyc29yLWdyYWJiaW5nJ1xuICAgICAgICAgICl9XG4gICAgICAgICAgb25Qb2ludGVyQ2FuY2VsPXtlbmREcmFnfVxuICAgICAgICAgIG9uUG9pbnRlckRvd249e29uRHJhZ1BvaW50ZXJEb3dufVxuICAgICAgICAgIG9uUG9pbnRlck1vdmU9e29uRHJhZ1BvaW50ZXJNb3ZlfVxuICAgICAgICAgIG9uUG9pbnRlclVwPXtlbmREcmFnfVxuICAgICAgICA+XG4gICAgICAgICAgPGRpdlxuICAgICAgICAgICAgYXJpYS1oaWRkZW5cbiAgICAgICAgICAgIGNsYXNzTmFtZT1cIm14LWF1dG8gaC0xIHctMTAgc2hyaW5rLTAgcm91bmRlZC1mdWxsIGJnLWN1cnJlbnQvMjBcIlxuICAgICAgICAgIC8+XG5cbiAgICAgICAgICA8VHlwb2dyYXBoeVxuICAgICAgICAgICAgY2xhc3NOYW1lPVwidGV4dC1bMC42NXJlbV0gdHJhY2tpbmctWzAuMTVlbV0gdXBwZXJjYXNlIHRleHQtbWlkZ3JvdW5kLzcwXCJcbiAgICAgICAgICAgIG1vbmR3ZXN0XG4gICAgICAgICAgPlxuICAgICAgICAgICAge3RpdGxlfVxuICAgICAgICAgIDwvVHlwb2dyYXBoeT5cbiAgICAgICAgPC9kaXY+XG5cbiAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJtaW4taC0wIGZsZXgtMSBvdmVyZmxvdy15LWF1dG8gb3ZlcnNjcm9sbC1jb250YWluXCI+XG4gICAgICAgICAge2NoaWxkcmVufVxuICAgICAgICA8L2Rpdj5cbiAgICAgIDwvZGl2PlxuICAgIDwvZGl2PixcbiAgICBkb2N1bWVudC5ib2R5XG4gIClcbn1cblxuaW50ZXJmYWNlIEJvdHRvbVNoZWV0UHJvcHMge1xuICBiYWNrZHJvcERpc21pc3NMYWJlbD86IHN0cmluZ1xuICBjaGlsZHJlbjogUmVhY3ROb2RlXG4gIG9uQ2xvc2U6ICgpID0+IHZvaWRcbiAgb3BlbjogYm9vbGVhblxuICB0aXRsZTogc3RyaW5nXG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBd0pNLGNBaUNFLFlBakNGO0FBdEpOO0FBQUEsRUFHRTtBQUFBLEVBQ0E7QUFBQSxFQUNBO0FBQUEsT0FDSztBQUNQLFNBQVMsb0JBQW9CO0FBRTdCLFNBQVMsVUFBVTtBQUNuQixTQUFTLGtCQUFrQjtBQUUzQixNQUFNLG9CQUFvQjtBQUMxQixNQUFNLG1CQUFtQjtBQUN6QixNQUFNLHNCQUFzQjtBQU9yQixnQkFBUyxZQUFZO0FBQUEsRUFDMUIsdUJBQXVCO0FBQUEsRUFDdkI7QUFBQSxFQUNBO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFDRixHQUFxQjtBQUNuQixRQUFNLENBQUMsY0FBYyxlQUFlLElBQUksU0FBUyxJQUFJO0FBQ3JELFFBQU0sQ0FBQyxTQUFTLFVBQVUsSUFBSSxTQUFTLEtBQUs7QUFDNUMsUUFBTSxDQUFDLGNBQWMsZUFBZSxJQUFJLFNBQVMsQ0FBQztB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
