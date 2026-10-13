"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import { useEffect, useId, useRef, useState } from "react";
import { cn } from "../../utils/index.js";
const font = "font-mondwest text-[.9375rem] leading-[1.4] tracking-[0.1875rem]";
export function DropdownMenu({
  className,
  direction = "down",
  onChange,
  options,
  value
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const anchor = `--dropdown-${id.replace(/:/g, "")}`;
  const panelStyle = {
    position: "fixed",
    positionAnchor: anchor,
    positionTryFallbacks: direction === "left" || direction === "right" ? "flip-inline, flip-block" : "flip-block, flip-inline",
    ...direction === "up" && {
      left: "calc(anchor(left) - 0.5rem)",
      top: "calc(anchor(top) + 1rem)",
      transform: "translateY(-100%)"
    },
    ...direction === "right" && {
      left: "calc(anchor(right))",
      top: "calc(anchor(top) - 0.5rem)"
    },
    ...direction === "left" && {
      left: "calc(anchor(left) - 1px)",
      top: "calc(anchor(top) - 0.5rem)",
      transform: "translateX(-100%)"
    },
    ...direction === "down" && {
      left: "calc(anchor(left) - 0.5rem)",
      top: "calc(anchor(top) - 0.5rem)"
    }
  };
  useEffect(() => {
    if (!open) {
      return;
    }
    const ac = new AbortController();
    document.addEventListener(
      "mousedown",
      (e) => {
        if (!ref.current?.contains(e.target)) {
          setOpen(false);
        }
      },
      { signal: ac.signal }
    );
    return () => ac.abort();
  }, [open]);
  return /* @__PURE__ */ jsxs(
    "span",
    {
      className: cn("relative inline-block align-top", className),
      ref,
      children: [
        /* @__PURE__ */ jsxs(
          "span",
          {
            className: cn(font, "inline-block cursor-pointer hover:underline"),
            onClick: () => setOpen(!open),
            style: { anchorName: anchor },
            children: [
              options.find((o) => o.value === value)?.label ?? value,
              " ",
              open ? "\u2191" : "\u2193"
            ]
          }
        ),
        open && /* @__PURE__ */ jsx(
          "div",
          {
            className: "bg-background-base z-50 flex flex-col",
            style: panelStyle,
            children: options.map((o) => /* @__PURE__ */ jsx(
              "span",
              {
                className: cn(
                  font,
                  "block cursor-pointer p-2 whitespace-nowrap",
                  o.value === value ? "underline" : "hover:bg-midground/10"
                ),
                onClick: () => {
                  onChange(o.value);
                  setOpen(false);
                },
                children: o.label
              },
              o.value
            ))
          }
        )
      ]
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZUVmZmVjdCwgdXNlSWQsIHVzZVJlZiwgdXNlU3RhdGUgfSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuY29uc3QgZm9udCA9ICdmb250LW1vbmR3ZXN0IHRleHQtWy45Mzc1cmVtXSBsZWFkaW5nLVsxLjRdIHRyYWNraW5nLVswLjE4NzVyZW1dJ1xuXG50eXBlIERpcmVjdGlvbiA9ICdkb3duJyB8ICd1cCcgfCAnbGVmdCcgfCAncmlnaHQnXG5cbnR5cGUgQW5jaG9yU3R5bGUgPSBSZWFjdC5DU1NQcm9wZXJ0aWVzICYgUmVjb3JkPHN0cmluZywgc3RyaW5nIHwgbnVtYmVyPlxuXG5leHBvcnQgZnVuY3Rpb24gRHJvcGRvd25NZW51PFQgZXh0ZW5kcyBzdHJpbmc+KHtcbiAgY2xhc3NOYW1lLFxuICBkaXJlY3Rpb24gPSAnZG93bicsXG4gIG9uQ2hhbmdlLFxuICBvcHRpb25zLFxuICB2YWx1ZVxufToge1xuICBjbGFzc05hbWU/OiBzdHJpbmdcbiAgZGlyZWN0aW9uPzogRGlyZWN0aW9uXG4gIG9uQ2hhbmdlOiAodmFsdWU6IFQpID0+IHZvaWRcbiAgb3B0aW9uczogeyBsYWJlbDogc3RyaW5nOyB2YWx1ZTogVCB9W11cbiAgdmFsdWU6IFRcbn0pIHtcbiAgY29uc3QgaWQgPSB1c2VJZCgpXG4gIGNvbnN0IFtvcGVuLCBzZXRPcGVuXSA9IHVzZVN0YXRlKGZhbHNlKVxuICBjb25zdCByZWYgPSB1c2VSZWY8SFRNTFNwYW5FbGVtZW50PihudWxsKVxuXG4gIGNvbnN0IGFuY2hvciA9IGAtLWRyb3Bkb3duLSR7aWQucmVwbGFjZSgvOi9nLCAnJyl9YFxuXG4gIGNvbnN0IHBhbmVsU3R5bGU6IEFuY2hvclN0eWxlID0ge1xuICAgIHBvc2l0aW9uOiAnZml4ZWQnLFxuICAgIHBvc2l0aW9uQW5jaG9yOiBhbmNob3IsXG4gICAgcG9zaXRpb25UcnlGYWxsYmFja3M6XG4gICAgICBkaXJlY3Rpb24gPT09ICdsZWZ0JyB8fCBkaXJlY3Rpb24gPT09ICdyaWdodCdcbiAgICAgICAgPyAnZmxpcC1pbmxpbmUsIGZsaXAtYmxvY2snXG4gICAgICAgIDogJ2ZsaXAtYmxvY2ssIGZsaXAtaW5saW5lJyxcbiAgICAuLi4oZGlyZWN0aW9uID09PSAndXAnICYmIHtcbiAgICAgIGxlZnQ6ICdjYWxjKGFuY2hvcihsZWZ0KSAtIDAuNXJlbSknLFxuICAgICAgdG9wOiAnY2FsYyhhbmNob3IodG9wKSArIDFyZW0pJyxcbiAgICAgIHRyYW5zZm9ybTogJ3RyYW5zbGF0ZVkoLTEwMCUpJ1xuICAgIH0pLFxuICAgIC4uLihkaXJlY3Rpb24gPT09ICdyaWdodCcgJiYge1xuICAgICAgbGVmdDogJ2NhbGMoYW5jaG9yKHJpZ2h0KSknLFxuICAgICAgdG9wOiAnY2FsYyhhbmNob3IodG9wKSAtIDAuNXJlbSknXG4gICAgfSksXG4gICAgLi4uKGRpcmVjdGlvbiA9PT0gJ2xlZnQnICYmIHtcbiAgICAgIGxlZnQ6ICdjYWxjKGFuY2hvcihsZWZ0KSAtIDFweCknLFxuICAgICAgdG9wOiAnY2FsYyhhbmNob3IodG9wKSAtIDAuNXJlbSknLFxuICAgICAgdHJhbnNmb3JtOiAndHJhbnNsYXRlWCgtMTAwJSknXG4gICAgfSksXG4gICAgLi4uKGRpcmVjdGlvbiA9PT0gJ2Rvd24nICYmIHtcbiAgICAgIGxlZnQ6ICdjYWxjKGFuY2hvcihsZWZ0KSAtIDAuNXJlbSknLFxuICAgICAgdG9wOiAnY2FsYyhhbmNob3IodG9wKSAtIDAuNXJlbSknXG4gICAgfSlcbiAgfVxuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgaWYgKCFvcGVuKSB7XG4gICAgICByZXR1cm5cbiAgICB9XG5cbiAgICBjb25zdCBhYyA9IG5ldyBBYm9ydENvbnRyb2xsZXIoKVxuICAgIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoXG4gICAgICAnbW91c2Vkb3duJyxcbiAgICAgIGUgPT4ge1xuICAgICAgICBpZiAoIXJlZi5jdXJyZW50Py5jb250YWlucyhlLnRhcmdldCBhcyBOb2RlKSkge1xuICAgICAgICAgIHNldE9wZW4oZmFsc2UpXG4gICAgICAgIH1cbiAgICAgIH0sXG4gICAgICB7IHNpZ25hbDogYWMuc2lnbmFsIH1cbiAgICApXG5cbiAgICByZXR1cm4gKCkgPT4gYWMuYWJvcnQoKVxuICB9LCBbb3Blbl0pXG5cbiAgcmV0dXJuIChcbiAgICA8c3BhblxuICAgICAgY2xhc3NOYW1lPXtjbigncmVsYXRpdmUgaW5saW5lLWJsb2NrIGFsaWduLXRvcCcsIGNsYXNzTmFtZSl9XG4gICAgICByZWY9e3JlZn1cbiAgICA+XG4gICAgICA8c3BhblxuICAgICAgICBjbGFzc05hbWU9e2NuKGZvbnQsICdpbmxpbmUtYmxvY2sgY3Vyc29yLXBvaW50ZXIgaG92ZXI6dW5kZXJsaW5lJyl9XG4gICAgICAgIG9uQ2xpY2s9eygpID0+IHNldE9wZW4oIW9wZW4pfVxuICAgICAgICBzdHlsZT17eyBhbmNob3JOYW1lOiBhbmNob3IgfSBhcyBBbmNob3JTdHlsZX1cbiAgICAgID5cbiAgICAgICAge29wdGlvbnMuZmluZChvID0+IG8udmFsdWUgPT09IHZhbHVlKT8ubGFiZWwgPz8gdmFsdWV9eycgJ31cbiAgICAgICAge29wZW4gPyAnXHUyMTkxJyA6ICdcdTIxOTMnfVxuICAgICAgPC9zcGFuPlxuXG4gICAgICB7b3BlbiAmJiAoXG4gICAgICAgIDxkaXZcbiAgICAgICAgICBjbGFzc05hbWU9XCJiZy1iYWNrZ3JvdW5kLWJhc2Ugei01MCBmbGV4IGZsZXgtY29sXCJcbiAgICAgICAgICBzdHlsZT17cGFuZWxTdHlsZX1cbiAgICAgICAgPlxuICAgICAgICAgIHtvcHRpb25zLm1hcChvID0+IChcbiAgICAgICAgICAgIDxzcGFuXG4gICAgICAgICAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICAgICAgICAgZm9udCxcbiAgICAgICAgICAgICAgICAnYmxvY2sgY3Vyc29yLXBvaW50ZXIgcC0yIHdoaXRlc3BhY2Utbm93cmFwJyxcbiAgICAgICAgICAgICAgICBvLnZhbHVlID09PSB2YWx1ZSA/ICd1bmRlcmxpbmUnIDogJ2hvdmVyOmJnLW1pZGdyb3VuZC8xMCdcbiAgICAgICAgICAgICAgKX1cbiAgICAgICAgICAgICAga2V5PXtvLnZhbHVlfVxuICAgICAgICAgICAgICBvbkNsaWNrPXsoKSA9PiB7XG4gICAgICAgICAgICAgICAgb25DaGFuZ2Uoby52YWx1ZSlcbiAgICAgICAgICAgICAgICBzZXRPcGVuKGZhbHNlKVxuICAgICAgICAgICAgICB9fVxuICAgICAgICAgICAgPlxuICAgICAgICAgICAgICB7by5sYWJlbH1cbiAgICAgICAgICAgIDwvc3Bhbj5cbiAgICAgICAgICApKX1cbiAgICAgICAgPC9kaXY+XG4gICAgICApfVxuICAgIDwvc3Bhbj5cbiAgKVxufVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQWtGTSxTQWVNLEtBZk47QUFoRk4sU0FBUyxXQUFXLE9BQU8sUUFBUSxnQkFBZ0I7QUFFbkQsU0FBUyxVQUFVO0FBRW5CLE1BQU0sT0FBTztBQU1OLGdCQUFTLGFBQStCO0FBQUEsRUFDN0M7QUFBQSxFQUNBLFlBQVk7QUFBQSxFQUNaO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFDRixHQU1HO0FBQ0QsUUFBTSxLQUFLLE1BQU07QUFDakIsUUFBTSxDQUFDLE1BQU0sT0FBTyxJQUFJLFNBQVMsS0FBSztBQUN0QyxRQUFNLE1BQU0sT0FBd0IsSUFBSTtBQUV4QyxRQUFNLFNBQVMsY0FBYyxHQUFHLFFBQVEsTUFBTSxFQUFFLENBQUM7QUFFakQsUUFBTSxhQUEwQjtBQUFBLElBQzlCLFVBQVU7QUFBQSxJQUNWLGdCQUFnQjtBQUFBLElBQ2hCLHNCQUNFLGNBQWMsVUFBVSxjQUFjLFVBQ2xDLDRCQUNBO0FBQUEsSUFDTixHQUFJLGNBQWMsUUFBUTtBQUFBLE1BQ3hCLE1BQU07QUFBQSxNQUNOLEtBQUs7QUFBQSxNQUNMLFdBQVc7QUFBQSxJQUNiO0FBQUEsSUFDQSxHQUFJLGNBQWMsV0FBVztBQUFBLE1BQzNCLE1BQU07QUFBQSxNQUNOLEtBQUs7QUFBQSxJQUNQO0FBQUEsSUFDQSxHQUFJLGNBQWMsVUFBVTtBQUFBLE1BQzFCLE1BQU07QUFBQSxNQUNOLEtBQUs7QUFBQSxNQUNMLFdBQVc7QUFBQSxJQUNiO0FBQUEsSUFDQSxHQUFJLGNBQWMsVUFBVTtBQUFBLE1BQzFCLE1BQU07QUFBQSxNQUNOLEtBQUs7QUFBQSxJQUNQO0FBQUEsRUFDRjtBQUVBLFlBQVUsTUFBTTtBQUNkLFFBQUksQ0FBQyxNQUFNO0FBQ1Q7QUFBQSxJQUNGO0FBRUEsVUFBTSxLQUFLLElBQUksZ0JBQWdCO0FBQy9CLGFBQVM7QUFBQSxNQUNQO0FBQUEsTUFDQSxPQUFLO0FBQ0gsWUFBSSxDQUFDLElBQUksU0FBUyxTQUFTLEVBQUUsTUFBYyxHQUFHO0FBQzVDLGtCQUFRLEtBQUs7QUFBQSxRQUNmO0FBQUEsTUFDRjtBQUFBLE1BQ0EsRUFBRSxRQUFRLEdBQUcsT0FBTztBQUFBLElBQ3RCO0FBRUEsV0FBTyxNQUFNLEdBQUcsTUFBTTtBQUFBLEVBQ3hCLEdBQUcsQ0FBQyxJQUFJLENBQUM7QUFFVCxTQUNFO0FBQUEsSUFBQztBQUFBO0FBQUEsTUFDQyxXQUFXLEdBQUcsbUNBQW1DLFNBQVM7QUFBQSxNQUMxRDtBQUFBLE1BRUE7QUFBQTtBQUFBLFVBQUM7QUFBQTtBQUFBLFlBQ0MsV0FBVyxHQUFHLE1BQU0sNkNBQTZDO0FBQUEsWUFDakUsU0FBUyxNQUFNLFFBQVEsQ0FBQyxJQUFJO0FBQUEsWUFDNUIsT0FBTyxFQUFFLFlBQVksT0FBTztBQUFBLFlBRTNCO0FBQUEsc0JBQVEsS0FBSyxPQUFLLEVBQUUsVUFBVSxLQUFLLEdBQUcsU0FBUztBQUFBLGNBQU87QUFBQSxjQUN0RCxPQUFPLFdBQU07QUFBQTtBQUFBO0FBQUEsUUFDaEI7QUFBQSxRQUVDLFFBQ0M7QUFBQSxVQUFDO0FBQUE7QUFBQSxZQUNDLFdBQVU7QUFBQSxZQUNWLE9BQU87QUFBQSxZQUVOLGtCQUFRLElBQUksT0FDWDtBQUFBLGNBQUM7QUFBQTtBQUFBLGdCQUNDLFdBQVc7QUFBQSxrQkFDVDtBQUFBLGtCQUNBO0FBQUEsa0JBQ0EsRUFBRSxVQUFVLFFBQVEsY0FBYztBQUFBLGdCQUNwQztBQUFBLGdCQUVBLFNBQVMsTUFBTTtBQUNiLDJCQUFTLEVBQUUsS0FBSztBQUNoQiwwQkFBUSxLQUFLO0FBQUEsZ0JBQ2Y7QUFBQSxnQkFFQyxZQUFFO0FBQUE7QUFBQSxjQU5FLEVBQUU7QUFBQSxZQU9ULENBQ0Q7QUFBQTtBQUFBLFFBQ0g7QUFBQTtBQUFBO0FBQUEsRUFFSjtBQUVKOyIsCiAgIm5hbWVzIjogW10KfQo=
