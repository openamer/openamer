"use client";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { cn } from "../../utils/index.js";
import { ImageDistortion } from "./image-distortion.js";
import { Typography } from "./typography/index.js";
export function TierCard({
  badge,
  bullets,
  className,
  image,
  isCurrent = false,
  onSelect,
  overlay,
  price,
  selected = false,
  tint,
  tintStrength,
  title
}) {
  return /* @__PURE__ */ jsxs(
    "button",
    {
      className: cn(
        "group relative flex w-full cursor-pointer flex-col border border-current/20",
        "text-left transition-colors duration-300",
        selected && "border-midground/60",
        isCurrent && !selected && "border-midground/30",
        className
      ),
      onClick: onSelect,
      type: "button",
      children: [
        /* @__PURE__ */ jsx(
          "span",
          {
            "aria-hidden": true,
            className: cn(
              "arc-border transition-opacity duration-200",
              selected ? "opacity-100" : "opacity-0 group-hover:opacity-100"
            )
          }
        ),
        /* @__PURE__ */ jsxs(
          "div",
          {
            className: "relative aspect-[3/4] min-h-0 w-full flex-1 overflow-hidden",
            style: { backgroundColor: "var(--background)" },
            children: [
              /* @__PURE__ */ jsx(
                ImageDistortion,
                {
                  active: selected,
                  src: image,
                  tint,
                  tintStrength
                }
              ),
              overlay && /* @__PURE__ */ jsx(
                "div",
                {
                  className: "pointer-events-none absolute inset-0",
                  style: { backgroundColor: overlay, mixBlendMode: "color" }
                }
              ),
              /* @__PURE__ */ jsxs("div", { className: "pointer-events-none absolute inset-0 z-[1] flex flex-col justify-between p-3", children: [
                /* @__PURE__ */ jsxs("div", { className: "flex flex-col gap-0.5", children: [
                  /* @__PURE__ */ jsxs(
                    Typography,
                    {
                      variant: "sm",
                      className: cn(
                        "block drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)] text-[1.2rem]",
                        "transition-colors",
                        selected && "text-midground"
                      ),
                      style: selected ? { mixBlendMode: "plus-lighter" } : void 0,
                      children: [
                        title,
                        badge && /* @__PURE__ */ jsx("span", { className: "ml-1 opacity-50", children: badge })
                      ]
                    }
                  ),
                  price.secondary ? /* @__PURE__ */ jsxs(Fragment, { children: [
                    /* @__PURE__ */ jsxs(
                      Typography,
                      {
                        className: "block text-md line-through opacity-50 drop-shadow-[0_1px_3px_rgba(0,0,0,0.6)]",
                        expanded: true,
                        style: { mixBlendMode: "plus-lighter" },
                        children: [
                          price.secondary,
                          price.secondarySuffix && /* @__PURE__ */ jsx("span", { className: "text-[1rem]", children: price.secondarySuffix })
                        ]
                      }
                    ),
                    /* @__PURE__ */ jsxs(
                      Typography,
                      {
                        className: "block text-xl font-bold drop-shadow-[0_1px_3px_rgba(0,0,0,0.6)]",
                        expanded: true,
                        style: { mixBlendMode: "plus-lighter" },
                        children: [
                          price.primary,
                          price.primarySuffix && /* @__PURE__ */ jsxs("span", { className: "text-[1rem] opacity-60", children: [
                            " ",
                            price.primarySuffix
                          ] })
                        ]
                      }
                    )
                  ] }) : /* @__PURE__ */ jsxs(
                    Typography,
                    {
                      className: "block text-xl font-bold drop-shadow-[0_1px_3px_rgba(0,0,0,0.6)]",
                      expanded: true,
                      style: { mixBlendMode: "plus-lighter" },
                      children: [
                        price.primary,
                        price.primarySuffix && /* @__PURE__ */ jsx("span", { className: "text-[1rem] opacity-60", children: price.primarySuffix })
                      ]
                    }
                  )
                ] }),
                bullets.length > 0 && /* @__PURE__ */ jsx("ul", { className: "flex flex-col gap-1", children: bullets.map((bullet, i) => /* @__PURE__ */ jsxs(
                  "li",
                  {
                    className: cn(
                      "font-courier text-display text-[1rem] leading-tight tracking-tight",
                      "drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)]"
                    ),
                    children: [
                      "\xB7 ",
                      bullet
                    ]
                  },
                  typeof bullet === "string" ? bullet : i
                )) })
              ] })
            ]
          }
        )
      ]
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IGNuIH0gZnJvbSAnLi4vLi4vdXRpbHMnXG5cbmltcG9ydCB7IEltYWdlRGlzdG9ydGlvbiB9IGZyb20gJy4vaW1hZ2UtZGlzdG9ydGlvbidcbmltcG9ydCB7IFR5cG9ncmFwaHkgfSBmcm9tICcuL3R5cG9ncmFwaHknXG5pbXBvcnQgeyBTbWFsbCB9IGZyb20gJy4vdHlwb2dyYXBoeS9zbWFsbCdcblxuLyoqXG4gKiBTZWxlY3RhYmxlIHRpZXIgLyBwcmljaW5nIGNhcmQuIEZ1bGwtYmxlZWQgZGlzdG9ydGVkIGltYWdlIGJhY2tncm91bmQsXG4gKiByZWFkYWJsZSBvdmVybGF5IHRleHQsIGFuZCBhbiBhbmltYXRlZCBgLmFyYy1ib3JkZXJgIHNoaW1tZXIgb24gdGhlXG4gKiBzZWxlY3RlZCBzdGF0ZS4gRnVsbHkgcHJlc2VudGF0aW9uYWwgXHUyMDE0IHRoZSBjb25zdW1lciBvd25zIHRoZSBkYXRhXG4gKiAodGllciBzY2hlbWEsIHByaWNlIGZvcm1hdHRpbmcsIHRpZXIgaW1hZ2VyeSAvIHRpbnRzKS5cbiAqXG4gKiBWaXN1YWwgc3RhdGVzOlxuICogLSBgc2VsZWN0ZWRgOiBicmlnaHRlbnMgdGhlIGRpc3RvcnRpb24sIGFjdGl2YXRlcyBgLmFyYy1ib3JkZXJgLCBhbmRcbiAqICAgY29tcG9zaXRlcyB0aGUgaGVhZGxpbmUgLyBwcmljZSB3aXRoIGBtaXgtYmxlbmQtbW9kZTogcGx1cy1saWdodGVyYFxuICogICBzbyB0aGUgdGV4dCBsaWZ0cyBvZmYgdGhlIGltYWdlIHJlZ2FyZGxlc3Mgb2YgdGludC5cbiAqIC0gYGlzQ3VycmVudGA6IHN1YnRsZSBtaWRncm91bmQtdGludGVkIGJvcmRlciBoaW50IChzdXBwcmVzc2VkIHdoZW5cbiAqICAgYHNlbGVjdGVkYCB3aW5zKS5cbiAqIC0gYG92ZXJsYXlgOiBvcHRpb25hbCB0b3AtbGF5ZXIgY29sb3IgYmxlbmRlZCB3aXRoIGBtaXgtYmxlbmQtbW9kZTpcbiAqICAgY29sb3JgIFx1MjAxNCB1c2VkIGZvciB0aGUgXCJoaWdoZXN0IHRpZXJcIiByZWQgdHJlYXRtZW50IG9uIHRvcCBvZiBhbnlcbiAqICAgYmFzZSB0aW50LlxuICovXG5leHBvcnQgZnVuY3Rpb24gVGllckNhcmQoe1xuICBiYWRnZSxcbiAgYnVsbGV0cyxcbiAgY2xhc3NOYW1lLFxuICBpbWFnZSxcbiAgaXNDdXJyZW50ID0gZmFsc2UsXG4gIG9uU2VsZWN0LFxuICBvdmVybGF5LFxuICBwcmljZSxcbiAgc2VsZWN0ZWQgPSBmYWxzZSxcbiAgdGludCxcbiAgdGludFN0cmVuZ3RoLFxuICB0aXRsZVxufTogVGllckNhcmRQcm9wcykge1xuICByZXR1cm4gKFxuICAgIDxidXR0b25cbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICdncm91cCByZWxhdGl2ZSBmbGV4IHctZnVsbCBjdXJzb3ItcG9pbnRlciBmbGV4LWNvbCBib3JkZXIgYm9yZGVyLWN1cnJlbnQvMjAnLFxuICAgICAgICAndGV4dC1sZWZ0IHRyYW5zaXRpb24tY29sb3JzIGR1cmF0aW9uLTMwMCcsXG4gICAgICAgIHNlbGVjdGVkICYmICdib3JkZXItbWlkZ3JvdW5kLzYwJyxcbiAgICAgICAgaXNDdXJyZW50ICYmICFzZWxlY3RlZCAmJiAnYm9yZGVyLW1pZGdyb3VuZC8zMCcsXG4gICAgICAgIGNsYXNzTmFtZVxuICAgICAgKX1cbiAgICAgIG9uQ2xpY2s9e29uU2VsZWN0fVxuICAgICAgdHlwZT1cImJ1dHRvblwiXG4gICAgPlxuICAgICAgPHNwYW5cbiAgICAgICAgYXJpYS1oaWRkZW5cbiAgICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgICAnYXJjLWJvcmRlciB0cmFuc2l0aW9uLW9wYWNpdHkgZHVyYXRpb24tMjAwJyxcbiAgICAgICAgICBzZWxlY3RlZCA/ICdvcGFjaXR5LTEwMCcgOiAnb3BhY2l0eS0wIGdyb3VwLWhvdmVyOm9wYWNpdHktMTAwJ1xuICAgICAgICApfVxuICAgICAgLz5cblxuICAgICAgPGRpdlxuICAgICAgICBjbGFzc05hbWU9XCJyZWxhdGl2ZSBhc3BlY3QtWzMvNF0gbWluLWgtMCB3LWZ1bGwgZmxleC0xIG92ZXJmbG93LWhpZGRlblwiXG4gICAgICAgIHN0eWxlPXt7IGJhY2tncm91bmRDb2xvcjogJ3ZhcigtLWJhY2tncm91bmQpJyB9fVxuICAgICAgPlxuICAgICAgICA8SW1hZ2VEaXN0b3J0aW9uXG4gICAgICAgICAgYWN0aXZlPXtzZWxlY3RlZH1cbiAgICAgICAgICBzcmM9e2ltYWdlfVxuICAgICAgICAgIHRpbnQ9e3RpbnR9XG4gICAgICAgICAgdGludFN0cmVuZ3RoPXt0aW50U3RyZW5ndGh9XG4gICAgICAgIC8+XG5cbiAgICAgICAge292ZXJsYXkgJiYgKFxuICAgICAgICAgIDxkaXZcbiAgICAgICAgICAgIGNsYXNzTmFtZT1cInBvaW50ZXItZXZlbnRzLW5vbmUgYWJzb2x1dGUgaW5zZXQtMFwiXG4gICAgICAgICAgICBzdHlsZT17eyBiYWNrZ3JvdW5kQ29sb3I6IG92ZXJsYXksIG1peEJsZW5kTW9kZTogJ2NvbG9yJyB9fVxuICAgICAgICAgIC8+XG4gICAgICAgICl9XG5cbiAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJwb2ludGVyLWV2ZW50cy1ub25lIGFic29sdXRlIGluc2V0LTAgei1bMV0gZmxleCBmbGV4LWNvbCBqdXN0aWZ5LWJldHdlZW4gcC0zXCI+XG4gICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGZsZXgtY29sIGdhcC0wLjVcIj5cbiAgICAgICAgICAgIDxUeXBvZ3JhcGh5IHZhcmlhbnQ9XCJzbVwiIFxuICAgICAgICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICAgICAgICdibG9jayBkcm9wLXNoYWRvdy1bMF8xcHhfMnB4X3JnYmEoMCwwLDAsMC41KV0gdGV4dC1bMS4ycmVtXScsXG4gICAgICAgICAgICAgICAgJ3RyYW5zaXRpb24tY29sb3JzJyxcbiAgICAgICAgICAgICAgICBzZWxlY3RlZCAmJiAndGV4dC1taWRncm91bmQnXG4gICAgICAgICAgICAgICl9XG4gICAgICAgICAgICAgIHN0eWxlPXtzZWxlY3RlZCA/IHsgbWl4QmxlbmRNb2RlOiAncGx1cy1saWdodGVyJyB9IDogdW5kZWZpbmVkfVxuICAgICAgICAgICAgPlxuICAgICAgICAgICAgICB7dGl0bGV9XG4gICAgICAgICAgICAgIHtiYWRnZSAmJiA8c3BhbiBjbGFzc05hbWU9XCJtbC0xIG9wYWNpdHktNTBcIj57YmFkZ2V9PC9zcGFuPn1cbiAgICAgICAgICAgIDwvVHlwb2dyYXBoeT5cblxuICAgICAgICAgICAge3ByaWNlLnNlY29uZGFyeSA/IChcbiAgICAgICAgICAgICAgPD5cbiAgICAgICAgICAgICAgICA8VHlwb2dyYXBoeVxuICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwiYmxvY2sgdGV4dC1tZCBsaW5lLXRocm91Z2ggb3BhY2l0eS01MCBkcm9wLXNoYWRvdy1bMF8xcHhfM3B4X3JnYmEoMCwwLDAsMC42KV1cIlxuICAgICAgICAgICAgICAgICAgZXhwYW5kZWRcbiAgICAgICAgICAgICAgICAgIHN0eWxlPXt7IG1peEJsZW5kTW9kZTogJ3BsdXMtbGlnaHRlcicgfX1cbiAgICAgICAgICAgICAgICA+XG4gICAgICAgICAgICAgICAgICB7cHJpY2Uuc2Vjb25kYXJ5fVxuICAgICAgICAgICAgICAgICAge3ByaWNlLnNlY29uZGFyeVN1ZmZpeCAmJiAoXG4gICAgICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzTmFtZT1cInRleHQtWzFyZW1dXCI+XG4gICAgICAgICAgICAgICAgICAgICAge3ByaWNlLnNlY29uZGFyeVN1ZmZpeH1cbiAgICAgICAgICAgICAgICAgICAgPC9zcGFuPlxuICAgICAgICAgICAgICAgICAgKX1cbiAgICAgICAgICAgICAgICA8L1R5cG9ncmFwaHk+XG5cbiAgICAgICAgICAgICAgICA8VHlwb2dyYXBoeVxuICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwiYmxvY2sgdGV4dC14bCBmb250LWJvbGQgZHJvcC1zaGFkb3ctWzBfMXB4XzNweF9yZ2JhKDAsMCwwLDAuNildXCJcbiAgICAgICAgICAgICAgICAgIGV4cGFuZGVkXG4gICAgICAgICAgICAgICAgICBzdHlsZT17eyBtaXhCbGVuZE1vZGU6ICdwbHVzLWxpZ2h0ZXInIH19XG4gICAgICAgICAgICAgICAgPlxuICAgICAgICAgICAgICAgICAge3ByaWNlLnByaW1hcnl9XG4gICAgICAgICAgICAgICAgICB7cHJpY2UucHJpbWFyeVN1ZmZpeCAmJiAoXG4gICAgICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzTmFtZT1cInRleHQtWzFyZW1dIG9wYWNpdHktNjBcIj5cbiAgICAgICAgICAgICAgICAgICAgICB7JyAnfVxuICAgICAgICAgICAgICAgICAgICAgIHtwcmljZS5wcmltYXJ5U3VmZml4fVxuICAgICAgICAgICAgICAgICAgICA8L3NwYW4+XG4gICAgICAgICAgICAgICAgICApfVxuICAgICAgICAgICAgICAgIDwvVHlwb2dyYXBoeT5cbiAgICAgICAgICAgICAgPC8+XG4gICAgICAgICAgICApIDogKFxuICAgICAgICAgICAgICA8VHlwb2dyYXBoeVxuICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cImJsb2NrIHRleHQteGwgZm9udC1ib2xkIGRyb3Atc2hhZG93LVswXzFweF8zcHhfcmdiYSgwLDAsMCwwLjYpXVwiXG4gICAgICAgICAgICAgICAgZXhwYW5kZWRcbiAgICAgICAgICAgICAgICBzdHlsZT17eyBtaXhCbGVuZE1vZGU6ICdwbHVzLWxpZ2h0ZXInIH19XG4gICAgICAgICAgICAgID5cbiAgICAgICAgICAgICAgICB7cHJpY2UucHJpbWFyeX1cbiAgICAgICAgICAgICAgICB7cHJpY2UucHJpbWFyeVN1ZmZpeCAmJiAoXG4gICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzc05hbWU9XCJ0ZXh0LVsxcmVtXSBvcGFjaXR5LTYwXCI+XG4gICAgICAgICAgICAgICAgICAgIHtwcmljZS5wcmltYXJ5U3VmZml4fVxuICAgICAgICAgICAgICAgICAgPC9zcGFuPlxuICAgICAgICAgICAgICAgICl9XG4gICAgICAgICAgICAgIDwvVHlwb2dyYXBoeT5cbiAgICAgICAgICAgICl9XG4gICAgICAgICAgPC9kaXY+XG5cbiAgICAgICAgICB7YnVsbGV0cy5sZW5ndGggPiAwICYmIChcbiAgICAgICAgICAgIDx1bCBjbGFzc05hbWU9XCJmbGV4IGZsZXgtY29sIGdhcC0xXCI+XG4gICAgICAgICAgICAgIHtidWxsZXRzLm1hcCgoYnVsbGV0LCBpKSA9PiAoXG4gICAgICAgICAgICAgICAgPGxpXG4gICAgICAgICAgICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICAgICAgICAgICAnZm9udC1jb3VyaWVyIHRleHQtZGlzcGxheSB0ZXh0LVsxcmVtXSBsZWFkaW5nLXRpZ2h0IHRyYWNraW5nLXRpZ2h0JyxcbiAgICAgICAgICAgICAgICAgICAgJ2Ryb3Atc2hhZG93LVswXzFweF8ycHhfcmdiYSgwLDAsMCwwLjUpXScsXG4gICAgICAgICAgICAgICAgICApfVxuICAgICAgICAgICAgICAgICAga2V5PXt0eXBlb2YgYnVsbGV0ID09PSAnc3RyaW5nJyA/IGJ1bGxldCA6IGl9XG4gICAgICAgICAgICAgICAgPlxuICAgICAgICAgICAgICAgICAgXHUwMEI3IHtidWxsZXR9XG4gICAgICAgICAgICAgICAgPC9saT5cbiAgICAgICAgICAgICAgKSl9XG4gICAgICAgICAgICA8L3VsPlxuICAgICAgICAgICl9XG4gICAgICAgIDwvZGl2PlxuICAgICAgPC9kaXY+XG4gICAgPC9idXR0b24+XG4gIClcbn1cblxuZXhwb3J0IGludGVyZmFjZSBUaWVyQ2FyZFByaWNlIHtcbiAgLyoqIEhlYWRsaW5lIHByaWNlLCBlLmcuIGBcIiQyMFwiYCBvciBgXCJGcmVlXCJgLiAqL1xuICBwcmltYXJ5OiBzdHJpbmdcbiAgLyoqIFNtYWxsIHN1ZmZpeCByZW5kZXJlZCBhZnRlciBgcHJpbWFyeWAsIGUuZy4gYFwiL21vXCJgIG9yIGBcImZpcnN0IHBheW1lbnRcImAuICovXG4gIHByaW1hcnlTdWZmaXg/OiBzdHJpbmdcbiAgLyoqIE9wdGlvbmFsIHN0cnVjay10aHJvdWdoIGNvbXBhcmlzb24gcHJpY2UgcmVuZGVyZWQgYWJvdmUgYHByaW1hcnlgLCBlLmcuIGBcIiQzMFwiYC4gKi9cbiAgc2Vjb25kYXJ5Pzogc3RyaW5nXG4gIC8qKiBTbWFsbCBzdWZmaXggcmVuZGVyZWQgYWZ0ZXIgYHNlY29uZGFyeWAuICovXG4gIHNlY29uZGFyeVN1ZmZpeD86IHN0cmluZ1xufVxuXG5leHBvcnQgaW50ZXJmYWNlIFRpZXJDYXJkUHJvcHMge1xuICAvKiogU21hbGwgYW5ub3RhdGlvbiBhZnRlciB0aGUgdGl0bGUsIGUuZy4gYFwiKGN1cnJlbnQpXCJgLiAqL1xuICBiYWRnZT86IFJlYWN0LlJlYWN0Tm9kZVxuICAvKiogRmVhdHVyZSBsaXN0IHJlbmRlcmVkIHVuZGVyIHRoZSBwcmljZS4gKi9cbiAgYnVsbGV0czogUmVhY3QuUmVhY3ROb2RlW11cbiAgY2xhc3NOYW1lPzogc3RyaW5nXG4gIC8qKiBCYWNrZ3JvdW5kIGltYWdlIFVSTC4gKi9cbiAgaW1hZ2U6IHN0cmluZ1xuICAvKiogQXBwbGllcyB0aGUgXCJjdXJyZW50IHBsYW5cIiBib3JkZXIgaGludCB3aGVuIG5vdCBgc2VsZWN0ZWRgLiAqL1xuICBpc0N1cnJlbnQ/OiBib29sZWFuXG4gIG9uU2VsZWN0PzogKCkgPT4gdm9pZFxuICAvKiogQ29sb3IgYmxlbmRlZCB3aXRoIGBtaXgtYmxlbmQtbW9kZTogY29sb3JgIG92ZXIgdGhlIGltYWdlICh1c2VkIGZvciB0aGUgaGlnaGVzdC10aWVyIHJlZCB0cmVhdG1lbnQpLiAqL1xuICBvdmVybGF5Pzogc3RyaW5nXG4gIHByaWNlOiBUaWVyQ2FyZFByaWNlXG4gIC8qKiBBcHBsaWVzIHNlbGVjdGVkIGNocm9tZSAoYXJjLWJvcmRlciBzaGltbWVyLCBhY3RpdmUgZGlzdG9ydGlvbiwgcGx1cy1saWdodGVyIHRleHQgYmxlbmQpLiAqL1xuICBzZWxlY3RlZD86IGJvb2xlYW5cbiAgLyoqIFNoYWRlciB0aW50IHBhc3NlZCB0aHJvdWdoIHRvIGBJbWFnZURpc3RvcnRpb25gLiAqL1xuICB0aW50Pzogc3RyaW5nXG4gIC8qKiBBY3RpdmUgLyBpbmFjdGl2ZSB0aW50IHN0cmVuZ3RoIHBhc3NlZCB0aHJvdWdoIHRvIGBJbWFnZURpc3RvcnRpb25gLiAqL1xuICB0aW50U3RyZW5ndGg/OiB7IGFjdGl2ZTogbnVtYmVyOyBpbmFjdGl2ZTogbnVtYmVyIH1cbiAgLyoqIFRpZXIgbmFtZSAvIGhlYWRsaW5lLiAqL1xuICB0aXRsZTogUmVhY3QuUmVhY3ROb2RlXG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBa0RNLFNBeUNRLFVBekNSLEtBNEJNLFlBNUJOO0FBaEROLFNBQVMsVUFBVTtBQUVuQixTQUFTLHVCQUF1QjtBQUNoQyxTQUFTLGtCQUFrQjtBQW1CcEIsZ0JBQVMsU0FBUztBQUFBLEVBQ3ZCO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFBQSxFQUNBO0FBQUEsRUFDQSxZQUFZO0FBQUEsRUFDWjtBQUFBLEVBQ0E7QUFBQSxFQUNBO0FBQUEsRUFDQSxXQUFXO0FBQUEsRUFDWDtBQUFBLEVBQ0E7QUFBQSxFQUNBO0FBQ0YsR0FBa0I7QUFDaEIsU0FDRTtBQUFBLElBQUM7QUFBQTtBQUFBLE1BQ0MsV0FBVztBQUFBLFFBQ1Q7QUFBQSxRQUNBO0FBQUEsUUFDQSxZQUFZO0FBQUEsUUFDWixhQUFhLENBQUMsWUFBWTtBQUFBLFFBQzFCO0FBQUEsTUFDRjtBQUFBLE1BQ0EsU0FBUztBQUFBLE1BQ1QsTUFBSztBQUFBLE1BRUw7QUFBQTtBQUFBLFVBQUM7QUFBQTtBQUFBLFlBQ0MsZUFBVztBQUFBLFlBQ1gsV0FBVztBQUFBLGNBQ1Q7QUFBQSxjQUNBLFdBQVcsZ0JBQWdCO0FBQUEsWUFDN0I7QUFBQTtBQUFBLFFBQ0Y7QUFBQSxRQUVBO0FBQUEsVUFBQztBQUFBO0FBQUEsWUFDQyxXQUFVO0FBQUEsWUFDVixPQUFPLEVBQUUsaUJBQWlCLG9CQUFvQjtBQUFBLFlBRTlDO0FBQUE7QUFBQSxnQkFBQztBQUFBO0FBQUEsa0JBQ0MsUUFBUTtBQUFBLGtCQUNSLEtBQUs7QUFBQSxrQkFDTDtBQUFBLGtCQUNBO0FBQUE7QUFBQSxjQUNGO0FBQUEsY0FFQyxXQUNDO0FBQUEsZ0JBQUM7QUFBQTtBQUFBLGtCQUNDLFdBQVU7QUFBQSxrQkFDVixPQUFPLEVBQUUsaUJBQWlCLFNBQVMsY0FBYyxRQUFRO0FBQUE7QUFBQSxjQUMzRDtBQUFBLGNBR0YscUJBQUMsU0FBSSxXQUFVLGdGQUNiO0FBQUEscUNBQUMsU0FBSSxXQUFVLHlCQUNiO0FBQUE7QUFBQSxvQkFBQztBQUFBO0FBQUEsc0JBQVcsU0FBUTtBQUFBLHNCQUNsQixXQUFXO0FBQUEsd0JBQ1Q7QUFBQSx3QkFDQTtBQUFBLHdCQUNBLFlBQVk7QUFBQSxzQkFDZDtBQUFBLHNCQUNBLE9BQU8sV0FBVyxFQUFFLGNBQWMsZUFBZSxJQUFJO0FBQUEsc0JBRXBEO0FBQUE7QUFBQSx3QkFDQSxTQUFTLG9CQUFDLFVBQUssV0FBVSxtQkFBbUIsaUJBQU07QUFBQTtBQUFBO0FBQUEsa0JBQ3JEO0FBQUEsa0JBRUMsTUFBTSxZQUNMLGlDQUNFO0FBQUE7QUFBQSxzQkFBQztBQUFBO0FBQUEsd0JBQ0MsV0FBVTtBQUFBLHdCQUNWLFVBQVE7QUFBQSx3QkFDUixPQUFPLEVBQUUsY0FBYyxlQUFlO0FBQUEsd0JBRXJDO0FBQUEsZ0NBQU07QUFBQSwwQkFDTixNQUFNLG1CQUNMLG9CQUFDLFVBQUssV0FBVSxlQUNiLGdCQUFNLGlCQUNUO0FBQUE7QUFBQTtBQUFBLG9CQUVKO0FBQUEsb0JBRUE7QUFBQSxzQkFBQztBQUFBO0FBQUEsd0JBQ0MsV0FBVTtBQUFBLHdCQUNWLFVBQVE7QUFBQSx3QkFDUixPQUFPLEVBQUUsY0FBYyxlQUFlO0FBQUEsd0JBRXJDO0FBQUEsZ0NBQU07QUFBQSwwQkFDTixNQUFNLGlCQUNMLHFCQUFDLFVBQUssV0FBVSwwQkFDYjtBQUFBO0FBQUEsNEJBQ0EsTUFBTTtBQUFBLDZCQUNUO0FBQUE7QUFBQTtBQUFBLG9CQUVKO0FBQUEscUJBQ0YsSUFFQTtBQUFBLG9CQUFDO0FBQUE7QUFBQSxzQkFDQyxXQUFVO0FBQUEsc0JBQ1YsVUFBUTtBQUFBLHNCQUNSLE9BQU8sRUFBRSxjQUFjLGVBQWU7QUFBQSxzQkFFckM7QUFBQSw4QkFBTTtBQUFBLHdCQUNOLE1BQU0saUJBQ0wsb0JBQUMsVUFBSyxXQUFVLDBCQUNiLGdCQUFNLGVBQ1Q7QUFBQTtBQUFBO0FBQUEsa0JBRUo7QUFBQSxtQkFFSjtBQUFBLGdCQUVDLFFBQVEsU0FBUyxLQUNoQixvQkFBQyxRQUFHLFdBQVUsdUJBQ1gsa0JBQVEsSUFBSSxDQUFDLFFBQVEsTUFDcEI7QUFBQSxrQkFBQztBQUFBO0FBQUEsb0JBQ0MsV0FBVztBQUFBLHNCQUNUO0FBQUEsc0JBQ0E7QUFBQSxvQkFDRjtBQUFBLG9CQUVEO0FBQUE7QUFBQSxzQkFDSTtBQUFBO0FBQUE7QUFBQSxrQkFGRSxPQUFPLFdBQVcsV0FBVyxTQUFTO0FBQUEsZ0JBRzdDLENBQ0QsR0FDSDtBQUFBLGlCQUVKO0FBQUE7QUFBQTtBQUFBLFFBQ0Y7QUFBQTtBQUFBO0FBQUEsRUFDRjtBQUVKOyIsCiAgIm5hbWVzIjogW10KfQo=
