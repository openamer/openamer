"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import {
  Children,
  isValidElement,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { cn } from "../../utils/index.js";
const TRIGGER_CN = "flex h-9 w-full items-center justify-between gap-2 border border-midground/15 bg-background/40 px-3 py-1 font-courier text-sm text-left text-midground transition-colors hover:border-midground/25 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/30 focus-visible:border-midground/30 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer";
const LISTBOX_CN = "absolute z-50 mt-1 w-full max-h-60 overflow-auto border border-midground/15 bg-background-base text-midground shadow-lg";
export function Select({
  children,
  className,
  disabled,
  id,
  onValueChange,
  placeholder,
  style,
  value
}) {
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef(null);
  const listRef = useRef(null);
  const options = useMemo(() => collectOptions(children), [children]);
  const selected = options.find((o) => o.value === value);
  const displayLabel = selected?.label ?? placeholder ?? value ?? "";
  const close = useCallback(() => {
    setOpen(false);
    setHighlightedIndex(-1);
  }, []);
  useEffect(() => {
    if (!open) return;
    const ac = new AbortController();
    document.addEventListener(
      "mousedown",
      (e) => {
        if (!containerRef.current?.contains(e.target)) close();
      },
      { signal: ac.signal }
    );
    return () => ac.abort();
  }, [open, close]);
  useEffect(() => {
    if (!open || highlightedIndex < 0) return;
    const el = listRef.current?.children[highlightedIndex];
    el?.scrollIntoView({ block: "nearest" });
  }, [open, highlightedIndex]);
  const handleKeyDown = (e) => {
    if (disabled) return;
    switch (e.key) {
      case "Enter":
      case " ":
        e.preventDefault();
        if (!open) {
          setOpen(true);
          setHighlightedIndex(options.findIndex((o) => o.value === value));
        } else if (highlightedIndex >= 0 && options[highlightedIndex]) {
          onValueChange?.(options[highlightedIndex].value);
          close();
        }
        break;
      case "ArrowDown":
        e.preventDefault();
        if (!open) {
          setOpen(true);
          setHighlightedIndex(options.findIndex((o) => o.value === value));
        } else {
          setHighlightedIndex((i) => Math.min(i + 1, options.length - 1));
        }
        break;
      case "ArrowUp":
        e.preventDefault();
        if (open) setHighlightedIndex((i) => Math.max(i - 1, 0));
        break;
      case "Home":
        if (open) {
          e.preventDefault();
          setHighlightedIndex(0);
        }
        break;
      case "End":
        if (open) {
          e.preventDefault();
          setHighlightedIndex(options.length - 1);
        }
        break;
      case "Escape":
        e.preventDefault();
        close();
        break;
    }
  };
  return /* @__PURE__ */ jsxs(
    "div",
    {
      className: cn("relative", className),
      id,
      ref: containerRef,
      style,
      children: [
        /* @__PURE__ */ jsxs(
          "button",
          {
            "aria-expanded": open,
            "aria-haspopup": "listbox",
            className: TRIGGER_CN,
            disabled,
            onClick: () => !disabled && setOpen((o) => !o),
            onKeyDown: handleKeyDown,
            role: "combobox",
            type: "button",
            children: [
              /* @__PURE__ */ jsx("span", { className: cn("truncate", !selected && "text-midground/50"), children: displayLabel }),
              /* @__PURE__ */ jsx(
                ChevronDownGlyph,
                {
                  className: cn(
                    "size-3 shrink-0 text-midground/60 transition-transform",
                    open && "rotate-180"
                  )
                }
              )
            ]
          }
        ),
        open && /* @__PURE__ */ jsx("div", { className: LISTBOX_CN, ref: listRef, role: "listbox", children: options.map((opt, i) => {
          const isSelected = opt.value === value;
          const isHighlighted = i === highlightedIndex;
          return /* @__PURE__ */ jsxs(
            "div",
            {
              "aria-selected": isSelected,
              className: cn(
                "flex cursor-pointer items-center gap-2 px-3 py-2",
                "font-courier text-sm transition-colors",
                isHighlighted && "bg-midground/10",
                isSelected ? "text-midground" : "text-midground/70"
              ),
              onClick: () => {
                onValueChange?.(opt.value);
                close();
              },
              onMouseEnter: () => setHighlightedIndex(i),
              role: "option",
              children: [
                /* @__PURE__ */ jsx(
                  CheckGlyph,
                  {
                    className: cn(
                      "size-3 shrink-0",
                      isSelected ? "opacity-100" : "opacity-0"
                    )
                  }
                ),
                /* @__PURE__ */ jsx("span", { className: "truncate", children: opt.label })
              ]
            },
            opt.value
          );
        }) })
      ]
    }
  );
}
export function SelectOption(_props) {
  return null;
}
const ChevronDownGlyph = ({ className }) => /* @__PURE__ */ jsx(
  "svg",
  {
    "aria-hidden": true,
    className,
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "square",
    strokeWidth: 1.5,
    viewBox: "0 0 12 12",
    children: /* @__PURE__ */ jsx("path", { d: "M2.5 4.5 6 8l3.5-3.5" })
  }
);
const CheckGlyph = ({ className }) => /* @__PURE__ */ jsx(
  "svg",
  {
    "aria-hidden": true,
    className,
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "square",
    strokeWidth: 1.5,
    viewBox: "0 0 12 12",
    children: /* @__PURE__ */ jsx("path", { d: "m2.5 6.5 2.5 2.5L9.5 3.5" })
  }
);
function collectOptions(children) {
  const out = [];
  Children.forEach(children, (child) => {
    if (!isValidElement(child)) return;
    const el = child;
    if (el.props.value !== void 0) {
      out.push({
        label: typeof el.props.children === "string" ? el.props.children : String(el.props.value),
        value: String(el.props.value)
      });
    } else if (el.props.children) {
      out.push(...collectOptions(el.props.children));
    }
  });
  return out;
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7XG4gIENoaWxkcmVuLFxuICBpc1ZhbGlkRWxlbWVudCxcbiAgdXNlQ2FsbGJhY2ssXG4gIHVzZUVmZmVjdCxcbiAgdXNlTWVtbyxcbiAgdXNlUmVmLFxuICB1c2VTdGF0ZSxcbiAgdHlwZSBDU1NQcm9wZXJ0aWVzLFxuICB0eXBlIEtleWJvYXJkRXZlbnQsXG4gIHR5cGUgUmVhY3RFbGVtZW50LFxuICB0eXBlIFJlYWN0Tm9kZVxufSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuY29uc3QgVFJJR0dFUl9DTiA9XG4gICdmbGV4IGgtOSB3LWZ1bGwgaXRlbXMtY2VudGVyIGp1c3RpZnktYmV0d2VlbiBnYXAtMiAnICtcbiAgJ2JvcmRlciBib3JkZXItbWlkZ3JvdW5kLzE1IGJnLWJhY2tncm91bmQvNDAgcHgtMyBweS0xICcgK1xuICAnZm9udC1jb3VyaWVyIHRleHQtc20gdGV4dC1sZWZ0IHRleHQtbWlkZ3JvdW5kIHRyYW5zaXRpb24tY29sb3JzICcgK1xuICAnaG92ZXI6Ym9yZGVyLW1pZGdyb3VuZC8yNSAnICtcbiAgJ2ZvY3VzLXZpc2libGU6b3V0bGluZS1ub25lIGZvY3VzLXZpc2libGU6cmluZy0xIGZvY3VzLXZpc2libGU6cmluZy1taWRncm91bmQvMzAgZm9jdXMtdmlzaWJsZTpib3JkZXItbWlkZ3JvdW5kLzMwICcgK1xuICAnZGlzYWJsZWQ6Y3Vyc29yLW5vdC1hbGxvd2VkIGRpc2FibGVkOm9wYWNpdHktNTAgJyArXG4gICdjdXJzb3ItcG9pbnRlcidcblxuY29uc3QgTElTVEJPWF9DTiA9XG4gICdhYnNvbHV0ZSB6LTUwIG10LTEgdy1mdWxsIG1heC1oLTYwIG92ZXJmbG93LWF1dG8gJyArXG4gICdib3JkZXIgYm9yZGVyLW1pZGdyb3VuZC8xNSBiZy1iYWNrZ3JvdW5kLWJhc2UgdGV4dC1taWRncm91bmQgc2hhZG93LWxnJ1xuXG5leHBvcnQgZnVuY3Rpb24gU2VsZWN0KHtcbiAgY2hpbGRyZW4sXG4gIGNsYXNzTmFtZSxcbiAgZGlzYWJsZWQsXG4gIGlkLFxuICBvblZhbHVlQ2hhbmdlLFxuICBwbGFjZWhvbGRlcixcbiAgc3R5bGUsXG4gIHZhbHVlXG59OiBTZWxlY3RQcm9wcykge1xuICBjb25zdCBbb3Blbiwgc2V0T3Blbl0gPSB1c2VTdGF0ZShmYWxzZSlcbiAgY29uc3QgW2hpZ2hsaWdodGVkSW5kZXgsIHNldEhpZ2hsaWdodGVkSW5kZXhdID0gdXNlU3RhdGUoLTEpXG4gIGNvbnN0IGNvbnRhaW5lclJlZiA9IHVzZVJlZjxIVE1MRGl2RWxlbWVudD4obnVsbClcbiAgY29uc3QgbGlzdFJlZiA9IHVzZVJlZjxIVE1MRGl2RWxlbWVudD4obnVsbClcblxuICBjb25zdCBvcHRpb25zID0gdXNlTWVtbygoKSA9PiBjb2xsZWN0T3B0aW9ucyhjaGlsZHJlbiksIFtjaGlsZHJlbl0pXG4gIGNvbnN0IHNlbGVjdGVkID0gb3B0aW9ucy5maW5kKG8gPT4gby52YWx1ZSA9PT0gdmFsdWUpXG4gIGNvbnN0IGRpc3BsYXlMYWJlbCA9IHNlbGVjdGVkPy5sYWJlbCA/PyBwbGFjZWhvbGRlciA/PyB2YWx1ZSA/PyAnJ1xuXG4gIGNvbnN0IGNsb3NlID0gdXNlQ2FsbGJhY2soKCkgPT4ge1xuICAgIHNldE9wZW4oZmFsc2UpXG4gICAgc2V0SGlnaGxpZ2h0ZWRJbmRleCgtMSlcbiAgfSwgW10pXG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBpZiAoIW9wZW4pIHJldHVyblxuICAgIGNvbnN0IGFjID0gbmV3IEFib3J0Q29udHJvbGxlcigpXG4gICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcihcbiAgICAgICdtb3VzZWRvd24nLFxuICAgICAgZSA9PiB7XG4gICAgICAgIGlmICghY29udGFpbmVyUmVmLmN1cnJlbnQ/LmNvbnRhaW5zKGUudGFyZ2V0IGFzIE5vZGUpKSBjbG9zZSgpXG4gICAgICB9LFxuICAgICAgeyBzaWduYWw6IGFjLnNpZ25hbCB9XG4gICAgKVxuICAgIHJldHVybiAoKSA9PiBhYy5hYm9ydCgpXG4gIH0sIFtvcGVuLCBjbG9zZV0pXG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBpZiAoIW9wZW4gfHwgaGlnaGxpZ2h0ZWRJbmRleCA8IDApIHJldHVyblxuICAgIGNvbnN0IGVsID0gbGlzdFJlZi5jdXJyZW50Py5jaGlsZHJlbltoaWdobGlnaHRlZEluZGV4XSBhc1xuICAgICAgfCBIVE1MRWxlbWVudFxuICAgICAgfCB1bmRlZmluZWRcbiAgICBlbD8uc2Nyb2xsSW50b1ZpZXcoeyBibG9jazogJ25lYXJlc3QnIH0pXG4gIH0sIFtvcGVuLCBoaWdobGlnaHRlZEluZGV4XSlcblxuICBjb25zdCBoYW5kbGVLZXlEb3duID0gKGU6IEtleWJvYXJkRXZlbnQpID0+IHtcbiAgICBpZiAoZGlzYWJsZWQpIHJldHVyblxuICAgIHN3aXRjaCAoZS5rZXkpIHtcbiAgICAgIGNhc2UgJ0VudGVyJzpcbiAgICAgIGNhc2UgJyAnOlxuICAgICAgICBlLnByZXZlbnREZWZhdWx0KClcbiAgICAgICAgaWYgKCFvcGVuKSB7XG4gICAgICAgICAgc2V0T3Blbih0cnVlKVxuICAgICAgICAgIHNldEhpZ2hsaWdodGVkSW5kZXgob3B0aW9ucy5maW5kSW5kZXgobyA9PiBvLnZhbHVlID09PSB2YWx1ZSkpXG4gICAgICAgIH0gZWxzZSBpZiAoaGlnaGxpZ2h0ZWRJbmRleCA+PSAwICYmIG9wdGlvbnNbaGlnaGxpZ2h0ZWRJbmRleF0pIHtcbiAgICAgICAgICBvblZhbHVlQ2hhbmdlPy4ob3B0aW9uc1toaWdobGlnaHRlZEluZGV4XS52YWx1ZSlcbiAgICAgICAgICBjbG9zZSgpXG4gICAgICAgIH1cbiAgICAgICAgYnJlYWtcbiAgICAgIGNhc2UgJ0Fycm93RG93bic6XG4gICAgICAgIGUucHJldmVudERlZmF1bHQoKVxuICAgICAgICBpZiAoIW9wZW4pIHtcbiAgICAgICAgICBzZXRPcGVuKHRydWUpXG4gICAgICAgICAgc2V0SGlnaGxpZ2h0ZWRJbmRleChvcHRpb25zLmZpbmRJbmRleChvID0+IG8udmFsdWUgPT09IHZhbHVlKSlcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBzZXRIaWdobGlnaHRlZEluZGV4KGkgPT4gTWF0aC5taW4oaSArIDEsIG9wdGlvbnMubGVuZ3RoIC0gMSkpXG4gICAgICAgIH1cbiAgICAgICAgYnJlYWtcbiAgICAgIGNhc2UgJ0Fycm93VXAnOlxuICAgICAgICBlLnByZXZlbnREZWZhdWx0KClcbiAgICAgICAgaWYgKG9wZW4pIHNldEhpZ2hsaWdodGVkSW5kZXgoaSA9PiBNYXRoLm1heChpIC0gMSwgMCkpXG4gICAgICAgIGJyZWFrXG4gICAgICBjYXNlICdIb21lJzpcbiAgICAgICAgaWYgKG9wZW4pIHtcbiAgICAgICAgICBlLnByZXZlbnREZWZhdWx0KClcbiAgICAgICAgICBzZXRIaWdobGlnaHRlZEluZGV4KDApXG4gICAgICAgIH1cbiAgICAgICAgYnJlYWtcbiAgICAgIGNhc2UgJ0VuZCc6XG4gICAgICAgIGlmIChvcGVuKSB7XG4gICAgICAgICAgZS5wcmV2ZW50RGVmYXVsdCgpXG4gICAgICAgICAgc2V0SGlnaGxpZ2h0ZWRJbmRleChvcHRpb25zLmxlbmd0aCAtIDEpXG4gICAgICAgIH1cbiAgICAgICAgYnJlYWtcbiAgICAgIGNhc2UgJ0VzY2FwZSc6XG4gICAgICAgIGUucHJldmVudERlZmF1bHQoKVxuICAgICAgICBjbG9zZSgpXG4gICAgICAgIGJyZWFrXG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIChcbiAgICA8ZGl2XG4gICAgICBjbGFzc05hbWU9e2NuKCdyZWxhdGl2ZScsIGNsYXNzTmFtZSl9XG4gICAgICBpZD17aWR9XG4gICAgICByZWY9e2NvbnRhaW5lclJlZn1cbiAgICAgIHN0eWxlPXtzdHlsZX1cbiAgICA+XG4gICAgICA8YnV0dG9uXG4gICAgICAgIGFyaWEtZXhwYW5kZWQ9e29wZW59XG4gICAgICAgIGFyaWEtaGFzcG9wdXA9XCJsaXN0Ym94XCJcbiAgICAgICAgY2xhc3NOYW1lPXtUUklHR0VSX0NOfVxuICAgICAgICBkaXNhYmxlZD17ZGlzYWJsZWR9XG4gICAgICAgIG9uQ2xpY2s9eygpID0+ICFkaXNhYmxlZCAmJiBzZXRPcGVuKG8gPT4gIW8pfVxuICAgICAgICBvbktleURvd249e2hhbmRsZUtleURvd259XG4gICAgICAgIHJvbGU9XCJjb21ib2JveFwiXG4gICAgICAgIHR5cGU9XCJidXR0b25cIlxuICAgICAgPlxuICAgICAgICA8c3BhbiBjbGFzc05hbWU9e2NuKCd0cnVuY2F0ZScsICFzZWxlY3RlZCAmJiAndGV4dC1taWRncm91bmQvNTAnKX0+XG4gICAgICAgICAge2Rpc3BsYXlMYWJlbH1cbiAgICAgICAgPC9zcGFuPlxuXG4gICAgICAgIDxDaGV2cm9uRG93bkdseXBoXG4gICAgICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgICAgICdzaXplLTMgc2hyaW5rLTAgdGV4dC1taWRncm91bmQvNjAgdHJhbnNpdGlvbi10cmFuc2Zvcm0nLFxuICAgICAgICAgICAgb3BlbiAmJiAncm90YXRlLTE4MCdcbiAgICAgICAgICApfVxuICAgICAgICAvPlxuICAgICAgPC9idXR0b24+XG5cbiAgICAgIHtvcGVuICYmIChcbiAgICAgICAgPGRpdiBjbGFzc05hbWU9e0xJU1RCT1hfQ059IHJlZj17bGlzdFJlZn0gcm9sZT1cImxpc3Rib3hcIj5cbiAgICAgICAgICB7b3B0aW9ucy5tYXAoKG9wdCwgaSkgPT4ge1xuICAgICAgICAgICAgY29uc3QgaXNTZWxlY3RlZCA9IG9wdC52YWx1ZSA9PT0gdmFsdWVcbiAgICAgICAgICAgIGNvbnN0IGlzSGlnaGxpZ2h0ZWQgPSBpID09PSBoaWdobGlnaHRlZEluZGV4XG5cbiAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgIDxkaXZcbiAgICAgICAgICAgICAgICBhcmlhLXNlbGVjdGVkPXtpc1NlbGVjdGVkfVxuICAgICAgICAgICAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICAgICAgICAgICAnZmxleCBjdXJzb3ItcG9pbnRlciBpdGVtcy1jZW50ZXIgZ2FwLTIgcHgtMyBweS0yJyxcbiAgICAgICAgICAgICAgICAgICdmb250LWNvdXJpZXIgdGV4dC1zbSB0cmFuc2l0aW9uLWNvbG9ycycsXG4gICAgICAgICAgICAgICAgICBpc0hpZ2hsaWdodGVkICYmICdiZy1taWRncm91bmQvMTAnLFxuICAgICAgICAgICAgICAgICAgaXNTZWxlY3RlZCA/ICd0ZXh0LW1pZGdyb3VuZCcgOiAndGV4dC1taWRncm91bmQvNzAnXG4gICAgICAgICAgICAgICAgKX1cbiAgICAgICAgICAgICAgICBrZXk9e29wdC52YWx1ZX1cbiAgICAgICAgICAgICAgICBvbkNsaWNrPXsoKSA9PiB7XG4gICAgICAgICAgICAgICAgICBvblZhbHVlQ2hhbmdlPy4ob3B0LnZhbHVlKVxuICAgICAgICAgICAgICAgICAgY2xvc2UoKVxuICAgICAgICAgICAgICAgIH19XG4gICAgICAgICAgICAgICAgb25Nb3VzZUVudGVyPXsoKSA9PiBzZXRIaWdobGlnaHRlZEluZGV4KGkpfVxuICAgICAgICAgICAgICAgIHJvbGU9XCJvcHRpb25cIlxuICAgICAgICAgICAgICA+XG4gICAgICAgICAgICAgICAgPENoZWNrR2x5cGhcbiAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICAgICAgICAgICAgICdzaXplLTMgc2hyaW5rLTAnLFxuICAgICAgICAgICAgICAgICAgICBpc1NlbGVjdGVkID8gJ29wYWNpdHktMTAwJyA6ICdvcGFjaXR5LTAnXG4gICAgICAgICAgICAgICAgICApfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAgPHNwYW4gY2xhc3NOYW1lPVwidHJ1bmNhdGVcIj57b3B0LmxhYmVsfTwvc3Bhbj5cbiAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICApXG4gICAgICAgICAgfSl9XG4gICAgICAgIDwvZGl2PlxuICAgICAgKX1cbiAgICA8L2Rpdj5cbiAgKVxufVxuXG4vLyBNYXJrZXIgY29tcG9uZW50IFx1MjAxNCBgU2VsZWN0YCByZWFkcyBgdmFsdWVgL2BjaGlsZHJlbmAgZnJvbSBpdHMgdHJlZS5cbi8vIFJlbmRlcnMgbm90aGluZyBvbiBpdHMgb3duLlxuZXhwb3J0IGZ1bmN0aW9uIFNlbGVjdE9wdGlvbihfcHJvcHM6IFNlbGVjdE9wdGlvblByb3BzKSB7XG4gIHJldHVybiBudWxsXG59XG5cbmNvbnN0IENoZXZyb25Eb3duR2x5cGggPSAoeyBjbGFzc05hbWUgfTogeyBjbGFzc05hbWU/OiBzdHJpbmcgfSkgPT4gKFxuICA8c3ZnXG4gICAgYXJpYS1oaWRkZW5cbiAgICBjbGFzc05hbWU9e2NsYXNzTmFtZX1cbiAgICBmaWxsPVwibm9uZVwiXG4gICAgc3Ryb2tlPVwiY3VycmVudENvbG9yXCJcbiAgICBzdHJva2VMaW5lY2FwPVwic3F1YXJlXCJcbiAgICBzdHJva2VXaWR0aD17MS41fVxuICAgIHZpZXdCb3g9XCIwIDAgMTIgMTJcIlxuICA+XG4gICAgPHBhdGggZD1cIk0yLjUgNC41IDYgOGwzLjUtMy41XCIgLz5cbiAgPC9zdmc+XG4pXG5cbmNvbnN0IENoZWNrR2x5cGggPSAoeyBjbGFzc05hbWUgfTogeyBjbGFzc05hbWU/OiBzdHJpbmcgfSkgPT4gKFxuICA8c3ZnXG4gICAgYXJpYS1oaWRkZW5cbiAgICBjbGFzc05hbWU9e2NsYXNzTmFtZX1cbiAgICBmaWxsPVwibm9uZVwiXG4gICAgc3Ryb2tlPVwiY3VycmVudENvbG9yXCJcbiAgICBzdHJva2VMaW5lY2FwPVwic3F1YXJlXCJcbiAgICBzdHJva2VXaWR0aD17MS41fVxuICAgIHZpZXdCb3g9XCIwIDAgMTIgMTJcIlxuICA+XG4gICAgPHBhdGggZD1cIm0yLjUgNi41IDIuNSAyLjVMOS41IDMuNVwiIC8+XG4gIDwvc3ZnPlxuKVxuXG5mdW5jdGlvbiBjb2xsZWN0T3B0aW9ucyhjaGlsZHJlbjogUmVhY3ROb2RlKTogU2VsZWN0T3B0aW9uRGF0YVtdIHtcbiAgY29uc3Qgb3V0OiBTZWxlY3RPcHRpb25EYXRhW10gPSBbXVxuICBDaGlsZHJlbi5mb3JFYWNoKGNoaWxkcmVuLCBjaGlsZCA9PiB7XG4gICAgaWYgKCFpc1ZhbGlkRWxlbWVudChjaGlsZCkpIHJldHVyblxuICAgIGNvbnN0IGVsID0gY2hpbGQgYXMgUmVhY3RFbGVtZW50PHtcbiAgICAgIGNoaWxkcmVuPzogUmVhY3ROb2RlXG4gICAgICB2YWx1ZT86IHVua25vd25cbiAgICB9PlxuICAgIGlmIChlbC5wcm9wcy52YWx1ZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBvdXQucHVzaCh7XG4gICAgICAgIGxhYmVsOlxuICAgICAgICAgIHR5cGVvZiBlbC5wcm9wcy5jaGlsZHJlbiA9PT0gJ3N0cmluZydcbiAgICAgICAgICAgID8gZWwucHJvcHMuY2hpbGRyZW5cbiAgICAgICAgICAgIDogU3RyaW5nKGVsLnByb3BzLnZhbHVlKSxcbiAgICAgICAgdmFsdWU6IFN0cmluZyhlbC5wcm9wcy52YWx1ZSlcbiAgICAgIH0pXG4gICAgfSBlbHNlIGlmIChlbC5wcm9wcy5jaGlsZHJlbikge1xuICAgICAgb3V0LnB1c2goLi4uY29sbGVjdE9wdGlvbnMoZWwucHJvcHMuY2hpbGRyZW4pKVxuICAgIH1cbiAgfSlcbiAgcmV0dXJuIG91dFxufVxuXG5pbnRlcmZhY2UgU2VsZWN0T3B0aW9uRGF0YSB7XG4gIGxhYmVsOiBzdHJpbmdcbiAgdmFsdWU6IHN0cmluZ1xufVxuXG5pbnRlcmZhY2UgU2VsZWN0T3B0aW9uUHJvcHMge1xuICBjaGlsZHJlbjogUmVhY3ROb2RlXG4gIHZhbHVlOiBzdHJpbmdcbn1cblxuaW50ZXJmYWNlIFNlbGVjdFByb3BzIHtcbiAgY2hpbGRyZW4/OiBSZWFjdE5vZGVcbiAgY2xhc3NOYW1lPzogc3RyaW5nXG4gIGRpc2FibGVkPzogYm9vbGVhblxuICBpZD86IHN0cmluZ1xuICBvblZhbHVlQ2hhbmdlPzogKHZhbHVlOiBzdHJpbmcpID0+IHZvaWRcbiAgcGxhY2Vob2xkZXI/OiBzdHJpbmdcbiAgc3R5bGU/OiBDU1NQcm9wZXJ0aWVzXG4gIHZhbHVlPzogc3RyaW5nXG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBaUlNLFNBVUUsS0FWRjtBQS9ITjtBQUFBLEVBQ0U7QUFBQSxFQUNBO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFBQSxFQUNBO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFBQSxPQUtLO0FBRVAsU0FBUyxVQUFVO0FBRW5CLE1BQU0sYUFDSjtBQVFGLE1BQU0sYUFDSjtBQUdLLGdCQUFTLE9BQU87QUFBQSxFQUNyQjtBQUFBLEVBQ0E7QUFBQSxFQUNBO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFBQSxFQUNBO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFDRixHQUFnQjtBQUNkLFFBQU0sQ0FBQyxNQUFNLE9BQU8sSUFBSSxTQUFTLEtBQUs7QUFDdEMsUUFBTSxDQUFDLGtCQUFrQixtQkFBbUIsSUFBSSxTQUFTLEVBQUU7QUFDM0QsUUFBTSxlQUFlLE9BQXVCLElBQUk7QUFDaEQsUUFBTSxVQUFVLE9BQXVCLElBQUk7QUFFM0MsUUFBTSxVQUFVLFFBQVEsTUFBTSxlQUFlLFFBQVEsR0FBRyxDQUFDLFFBQVEsQ0FBQztBQUNsRSxRQUFNLFdBQVcsUUFBUSxLQUFLLE9BQUssRUFBRSxVQUFVLEtBQUs7QUFDcEQsUUFBTSxlQUFlLFVBQVUsU0FBUyxlQUFlLFNBQVM7QUFFaEUsUUFBTSxRQUFRLFlBQVksTUFBTTtBQUM5QixZQUFRLEtBQUs7QUFDYix3QkFBb0IsRUFBRTtBQUFBLEVBQ3hCLEdBQUcsQ0FBQyxDQUFDO0FBRUwsWUFBVSxNQUFNO0FBQ2QsUUFBSSxDQUFDLEtBQU07QUFDWCxVQUFNLEtBQUssSUFBSSxnQkFBZ0I7QUFDL0IsYUFBUztBQUFBLE1BQ1A7QUFBQSxNQUNBLE9BQUs7QUFDSCxZQUFJLENBQUMsYUFBYSxTQUFTLFNBQVMsRUFBRSxNQUFjLEVBQUcsT0FBTTtBQUFBLE1BQy9EO0FBQUEsTUFDQSxFQUFFLFFBQVEsR0FBRyxPQUFPO0FB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
