import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { cva } from "class-variance-authority";
import { cloneElement } from "react";
import { cn } from "../../utils/index.js";
import { Typography } from "./typography/index.js";
const SHADOW_DEFAULT = "shadow-[inset_-1px_-1px_0_0_#00000080,inset_1px_1px_0_0_#ffffff80]";
const SHADOW_INVERT = "shadow-[inset_-1px_-1px_0_0_#00000080,inset_1px_1px_0_0_#ffffff29]";
const SHADOW_INVERT_OUTLINED = "shadow-[inset_-1px_-1px_0_0_#ffffff12,inset_1px_1px_0_0_#ffffff29]";
const ACTIVE_FILTER = "active:[filter:invert(1)_brightness(calc(100-99*var(--foreground-alpha,0)))]";
const buttonVariants = cva(
  [
    "group relative grid cursor-pointer grid-cols-[auto_1fr_auto] items-center",
    "text-display leading-0 font-bold tracking-[0.2em]",
    "disabled:pointer-events-none disabled:bg-midground/15 disabled:text-midground disabled:shadow-none"
  ],
  {
    compoundVariants: [
      // ── invert × outlined matrix (default surface, no ghost/destructive) ──
      {
        class: `bg-midground text-background-base active:invert ${SHADOW_DEFAULT}`,
        destructive: false,
        ghost: false,
        invert: false,
        outlined: false
      },
      {
        class: `bg-midground/15 text-midground ${SHADOW_INVERT} ${ACTIVE_FILTER}`,
        destructive: false,
        ghost: false,
        invert: true,
        outlined: false
      },
      {
        class: `shadow-midground ${SHADOW_DEFAULT} ${ACTIVE_FILTER}`,
        destructive: false,
        ghost: false,
        invert: false,
        outlined: true
      },
      {
        class: `${SHADOW_INVERT_OUTLINED} ${ACTIVE_FILTER}`,
        destructive: false,
        ghost: false,
        invert: true,
        outlined: true
      },
      // ── ghost: no chrome, hover bg only ──
      {
        class: "bg-transparent text-current hover:bg-midground/10 shadow-none",
        destructive: false,
        ghost: true
      },
      {
        class: "bg-transparent text-destructive hover:bg-destructive/10 shadow-none",
        destructive: true,
        ghost: true
      },
      // ── solid destructive ──
      {
        class: `bg-destructive text-destructive-foreground hover:bg-destructive/90 ${SHADOW_INVERT}`,
        destructive: true,
        ghost: false,
        outlined: false
      },
      // ── outlined destructive ──
      {
        class: "border border-destructive/40 bg-transparent text-destructive hover:bg-destructive/10 shadow-none",
        destructive: true,
        ghost: false,
        outlined: true
      }
    ],
    defaultVariants: {
      destructive: false,
      ghost: false,
      invert: false,
      outlined: false,
      size: "default"
    },
    variants: {
      destructive: { true: "" },
      ghost: { true: "" },
      invert: { true: "" },
      outlined: { true: "text-midground bg-transparent" },
      size: {
        default: "px-[.9em_.75em] py-[1.25em]",
        icon: "p-2 aspect-square grid-cols-1 place-items-center [&>svg]:size-3.5",
        sm: "px-3 py-1.5 text-[0.7rem] tracking-[0.15em] [&>svg]:size-3",
        xs: "p-1 aspect-square grid-cols-1 place-items-center [&>svg]:size-3"
      }
    }
  }
);
const IconSlot = ({
  icon,
  side
}) => /* @__PURE__ */ jsxs(Fragment, { children: [
  /* @__PURE__ */ jsx("span", { className: "w-5" }),
  /* @__PURE__ */ jsx(
    "span",
    {
      className: cn(
        "absolute top-1/2 -translate-y-1/2",
        side === "left" ? "left-3" : "right-3"
      ),
      children: typeof icon === "object" ? cloneElement(icon, {
        className: "size-3.5"
      }) : icon
    }
  )
] });
export const Button = ({
  children,
  className,
  destructive,
  ghost,
  invert,
  outlined,
  prefix,
  size,
  suffix,
  ...props
}) => /* @__PURE__ */ jsxs(
  Typography,
  {
    as: "button",
    className: cn(
      buttonVariants({ destructive, ghost, invert, outlined, size }),
      className
    ),
    mono: true,
    ...props,
    children: [
      !ghost && /* @__PURE__ */ jsx(
        "span",
        {
          "aria-hidden": true,
          className: "arc-border opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-visible:opacity-100 group-active:opacity-100"
        }
      ),
      prefix && /* @__PURE__ */ jsx(IconSlot, { icon: prefix, side: "left" }),
      children,
      suffix && /* @__PURE__ */ jsx(IconSlot, { icon: suffix, side: "right" })
    ]
  }
);
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgY3ZhLCB0eXBlIFZhcmlhbnRQcm9wcyB9IGZyb20gJ2NsYXNzLXZhcmlhbmNlLWF1dGhvcml0eSdcbmltcG9ydCB7IGNsb25lRWxlbWVudCB9IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyBjbiB9IGZyb20gJy4uLy4uL3V0aWxzJ1xuXG5pbXBvcnQgeyBUeXBvZ3JhcGh5IH0gZnJvbSAnLi90eXBvZ3JhcGh5J1xuXG5jb25zdCBTSEFET1dfREVGQVVMVCA9XG4gICdzaGFkb3ctW2luc2V0Xy0xcHhfLTFweF8wXzBfIzAwMDAwMDgwLGluc2V0XzFweF8xcHhfMF8wXyNmZmZmZmY4MF0nXG5jb25zdCBTSEFET1dfSU5WRVJUID1cbiAgJ3NoYWRvdy1baW5zZXRfLTFweF8tMXB4XzBfMF8jMDAwMDAwODAsaW5zZXRfMXB4XzFweF8wXzBfI2ZmZmZmZjI5XSdcbmNvbnN0IFNIQURPV19JTlZFUlRfT1VUTElORUQgPVxuICAnc2hhZG93LVtpbnNldF8tMXB4Xy0xcHhfMF8wXyNmZmZmZmYxMixpbnNldF8xcHhfMXB4XzBfMF8jZmZmZmZmMjldJ1xuY29uc3QgQUNUSVZFX0ZJTFRFUiA9XG4gICdhY3RpdmU6W2ZpbHRlcjppbnZlcnQoMSlfYnJpZ2h0bmVzcyhjYWxjKDEwMC05OSp2YXIoLS1mb3JlZ3JvdW5kLWFscGhhLDApKSldJ1xuXG5jb25zdCBidXR0b25WYXJpYW50cyA9IGN2YShcbiAgW1xuICAgICdncm91cCByZWxhdGl2ZSBncmlkIGN1cnNvci1wb2ludGVyIGdyaWQtY29scy1bYXV0b18xZnJfYXV0b10gaXRlbXMtY2VudGVyJyxcbiAgICAndGV4dC1kaXNwbGF5IGxlYWRpbmctMCBmb250LWJvbGQgdHJhY2tpbmctWzAuMmVtXScsXG4gICAgJ2Rpc2FibGVkOnBvaW50ZXItZXZlbnRzLW5vbmUgZGlzYWJsZWQ6YmctbWlkZ3JvdW5kLzE1IGRpc2FibGVkOnRleHQtbWlkZ3JvdW5kIGRpc2FibGVkOnNoYWRvdy1ub25lJ1xuICBdLFxuICB7XG4gICAgY29tcG91bmRWYXJpYW50czogW1xuICAgICAgLy8gXHUyNTAwXHUyNTAwIGludmVydCBcdTAwRDcgb3V0bGluZWQgbWF0cml4IChkZWZhdWx0IHN1cmZhY2UsIG5vIGdob3N0L2Rlc3RydWN0aXZlKSBcdTI1MDBcdTI1MDBcbiAgICAgIHtcbiAgICAgICAgY2xhc3M6IGBiZy1taWRncm91bmQgdGV4dC1iYWNrZ3JvdW5kLWJhc2UgYWN0aXZlOmludmVydCAke1NIQURPV19ERUZBVUxUfWAsXG4gICAgICAgIGRlc3RydWN0aXZlOiBmYWxzZSxcbiAgICAgICAgZ2hvc3Q6IGZhbHNlLFxuICAgICAgICBpbnZlcnQ6IGZhbHNlLFxuICAgICAgICBvdXRsaW5lZDogZmFsc2VcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIGNsYXNzOiBgYmctbWlkZ3JvdW5kLzE1IHRleHQtbWlkZ3JvdW5kICR7U0hBRE9XX0lOVkVSVH0gJHtBQ1RJVkVfRklMVEVSfWAsXG4gICAgICAgIGRlc3RydWN0aXZlOiBmYWxzZSxcbiAgICAgICAgZ2hvc3Q6IGZhbHNlLFxuICAgICAgICBpbnZlcnQ6IHRydWUsXG4gICAgICAgIG91dGxpbmVkOiBmYWxzZVxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgY2xhc3M6IGBzaGFkb3ctbWlkZ3JvdW5kICR7U0hBRE9XX0RFRkFVTFR9ICR7QUNUSVZFX0ZJTFRFUn1gLFxuICAgICAgICBkZXN0cnVjdGl2ZTogZmFsc2UsXG4gICAgICAgIGdob3N0OiBmYWxzZSxcbiAgICAgICAgaW52ZXJ0OiBmYWxzZSxcbiAgICAgICAgb3V0bGluZWQ6IHRydWVcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIGNsYXNzOiBgJHtTSEFET1dfSU5WRVJUX09VVExJTkVEfSAke0FDVElWRV9GSUxURVJ9YCxcbiAgICAgICAgZGVzdHJ1Y3RpdmU6IGZhbHNlLFxuICAgICAgICBnaG9zdDogZmFsc2UsXG4gICAgICAgIGludmVydDogdHJ1ZSxcbiAgICAgICAgb3V0bGluZWQ6IHRydWVcbiAgICAgIH0sXG4gICAgICAvLyBcdTI1MDBcdTI1MDAgZ2hvc3Q6IG5vIGNocm9tZSwgaG92ZXIgYmcgb25seSBcdTI1MDBcdTI1MDBcbiAgICAgIHtcbiAgICAgICAgY2xhc3M6ICdiZy10cmFuc3BhcmVudCB0ZXh0LWN1cnJlbnQgaG92ZXI6YmctbWlkZ3JvdW5kLzEwIHNoYWRvdy1ub25lJyxcbiAgICAgICAgZGVzdHJ1Y3RpdmU6IGZhbHNlLFxuICAgICAgICBnaG9zdDogdHJ1ZVxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgY2xhc3M6XG4gICAgICAgICAgJ2JnLXRyYW5zcGFyZW50IHRleHQtZGVzdHJ1Y3RpdmUgaG92ZXI6YmctZGVzdHJ1Y3RpdmUvMTAgc2hhZG93LW5vbmUnLFxuICAgICAgICBkZXN0cnVjdGl2ZTogdHJ1ZSxcbiAgICAgICAgZ2hvc3Q6IHRydWVcbiAgICAgIH0sXG4gICAgICAvLyBcdTI1MDBcdTI1MDAgc29saWQgZGVzdHJ1Y3RpdmUgXHUyNTAwXHUyNTAwXG4gICAgICB7XG4gICAgICAgIGNsYXNzOiBgYmctZGVzdHJ1Y3RpdmUgdGV4dC1kZXN0cnVjdGl2ZS1mb3JlZ3JvdW5kIGhvdmVyOmJnLWRlc3RydWN0aXZlLzkwICR7U0hBRE9XX0lOVkVSVH1gLFxuICAgICAgICBkZXN0cnVjdGl2ZTogdHJ1ZSxcbiAgICAgICAgZ2hvc3Q6IGZhbHNlLFxuICAgICAgICBvdXRsaW5lZDogZmFsc2VcbiAgICAgIH0sXG4gICAgICAvLyBcdTI1MDBcdTI1MDAgb3V0bGluZWQgZGVzdHJ1Y3RpdmUgXHUyNTAwXHUyNTAwXG4gICAgICB7XG4gICAgICAgIGNsYXNzOlxuICAgICAgICAgICdib3JkZXIgYm9yZGVyLWRlc3RydWN0aXZlLzQwIGJnLXRyYW5zcGFyZW50IHRleHQtZGVzdHJ1Y3RpdmUgaG92ZXI6YmctZGVzdHJ1Y3RpdmUvMTAgc2hhZG93LW5vbmUnLFxuICAgICAgICBkZXN0cnVjdGl2ZTogdHJ1ZSxcbiAgICAgICAgZ2hvc3Q6IGZhbHNlLFxuICAgICAgICBvdXRsaW5lZDogdHJ1ZVxuICAgICAgfVxuICAgIF0sXG4gICAgZGVmYXVsdFZhcmlhbnRzOiB7XG4gICAgICBkZXN0cnVjdGl2ZTogZmFsc2UsXG4gICAgICBnaG9zdDogZmFsc2UsXG4gICAgICBpbnZlcnQ6IGZhbHNlLFxuICAgICAgb3V0bGluZWQ6IGZhbHNlLFxuICAgICAgc2l6ZTogJ2RlZmF1bHQnXG4gICAgfSxcbiAgICB2YXJpYW50czoge1xuICAgICAgZGVzdHJ1Y3RpdmU6IHsgdHJ1ZTogJycgfSxcbiAgICAgIGdob3N0OiB7IHRydWU6ICcnIH0sXG4gICAgICBpbnZlcnQ6IHsgdHJ1ZTogJycgfSxcbiAgICAgIG91dGxpbmVkOiB7IHRydWU6ICd0ZXh0LW1pZGdyb3VuZCBiZy10cmFuc3BhcmVudCcgfSxcbiAgICAgIHNpemU6IHtcbiAgICAgICAgZGVmYXVsdDogJ3B4LVsuOWVtXy43NWVtXSBweS1bMS4yNWVtXScsXG4gICAgICAgIGljb246ICdwLTIgYXNwZWN0LXNxdWFyZSBncmlkLWNvbHMtMSBwbGFjZS1pdGVtcy1jZW50ZXIgWyY+c3ZnXTpzaXplLTMuNScsXG4gICAgICAgIHNtOiAncHgtMyBweS0xLjUgdGV4dC1bMC43cmVtXSB0cmFja2luZy1bMC4xNWVtXSBbJj5zdmddOnNpemUtMycsXG4gICAgICAgIHhzOiAncC0xIGFzcGVjdC1zcXVhcmUgZ3JpZC1jb2xzLTEgcGxhY2UtaXRlbXMtY2VudGVyIFsmPnN2Z106c2l6ZS0zJ1xuICAgICAgfVxuICAgIH1cbiAgfVxuKVxuXG5jb25zdCBJY29uU2xvdCA9ICh7XG4gIGljb24sXG4gIHNpZGVcbn06IHtcbiAgaWNvbjogUmVhY3QuUmVhY3ROb2RlXG4gIHNpZGU6ICdsZWZ0JyB8ICdyaWdodCdcbn0pID0+IChcbiAgPD5cbiAgICA8c3BhbiBjbGFzc05hbWU9XCJ3LTVcIiAvPlxuXG4gICAgPHNwYW5cbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICdhYnNvbHV0ZSB0b3AtMS8yIC10cmFuc2xhdGUteS0xLzInLFxuICAgICAgICBzaWRlID09PSAnbGVmdCcgPyAnbGVmdC0zJyA6ICdyaWdodC0zJ1xuICAgICAgKX1cbiAgICA+XG4gICAgICB7dHlwZW9mIGljb24gPT09ICdvYmplY3QnXG4gICAgICAgID8gY2xvbmVFbGVtZW50KGljb24gYXMgUmVhY3QuUmVhY3RFbGVtZW50PGFueT4sIHtcbiAgICAgICAgICAgIGNsYXNzTmFtZTogJ3NpemUtMy41J1xuICAgICAgICAgIH0pXG4gICAgICAgIDogaWNvbn1cbiAgICA8L3NwYW4+XG4gIDwvPlxuKVxuXG5leHBvcnQgY29uc3QgQnV0dG9uID0gKHtcbiAgY2hpbGRyZW4sXG4gIGNsYXNzTmFtZSxcbiAgZGVzdHJ1Y3RpdmUsXG4gIGdob3N0LFxuICBpbnZlcnQsXG4gIG91dGxpbmVkLFxuICBwcmVmaXgsXG4gIHNpemUsXG4gIHN1ZmZpeCxcbiAgLi4ucHJvcHNcbn06IEJ1dHRvblByb3BzKSA9PiAoXG4gIDxUeXBvZ3JhcGh5XG4gICAgYXM9XCJidXR0b25cIlxuICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICBidXR0b25WYXJpYW50cyh7IGRlc3RydWN0aXZlLCBnaG9zdCwgaW52ZXJ0LCBvdXRsaW5lZCwgc2l6ZSB9KSxcbiAgICAgIGNsYXNzTmFtZVxuICAgICl9XG4gICAgbW9ub1xuICAgIHsuLi5wcm9wc31cbiAgPlxuICAgIHshZ2hvc3QgJiYgKFxuICAgICAgPHNwYW5cbiAgICAgICAgYXJpYS1oaWRkZW5cbiAgICAgICAgY2xhc3NOYW1lPVwiYXJjLWJvcmRlciBvcGFjaXR5LTAgdHJhbnNpdGlvbi1vcGFjaXR5IGR1cmF0aW9uLTIwMCBncm91cC1ob3ZlcjpvcGFjaXR5LTEwMCBncm91cC1mb2N1cy12aXNpYmxlOm9wYWNpdHktMTAwIGdyb3VwLWFjdGl2ZTpvcGFjaXR5LTEwMFwiXG4gICAgICAvPlxuICAgICl9XG4gICAge3ByZWZpeCAmJiA8SWNvblNsb3QgaWNvbj17cHJlZml4fSBzaWRlPVwibGVmdFwiIC8+fVxuICAgIHtjaGlsZHJlbn1cbiAgICB7c3VmZml4ICYmIDxJY29uU2xvdCBpY29uPXtzdWZmaXh9IHNpZGU9XCJyaWdodFwiIC8+fVxuICA8L1R5cG9ncmFwaHk+XG4pXG5cbmludGVyZmFjZSBCdXR0b25Qcm9wc1xuICBleHRlbmRzIE9taXQ8XG4gICAgICBSZWFjdC5CdXR0b25IVE1MQXR0cmlidXRlczxIVE1MQnV0dG9uRWxlbWVudD4sXG4gICAgICAncHJlZml4JyB8ICdzdWZmaXgnXG4gICAgPixcbiAgICBWYXJpYW50UHJvcHM8dHlwZW9mIGJ1dHRvblZhcmlhbnRzPiB7XG4gIHByZWZpeD86IFJlYWN0LlJlYWN0Tm9kZVxuICBzdWZmaXg/OiBSZWFjdC5SZWFjdE5vZGVcbn1cbiJdLAogICJtYXBwaW5ncyI6ICJBQThHRSxtQkFDRSxLQURGO0FBOUdGLFNBQVMsV0FBOEI7QUFDdkMsU0FBUyxvQkFBb0I7QUFFN0IsU0FBUyxVQUFVO0FBRW5CLFNBQVMsa0JBQWtCO0FBRTNCLE1BQU0saUJBQ0o7QUFDRixNQUFNLGdCQUNKO0FBQ0YsTUFBTSx5QkFDSjtBQUNGLE1BQU0sZ0JBQ0o7QUFFRixNQUFNLGlCQUFpQjtBQUFBLEVBQ3JCO0FBQUEsSUFDRTtBQUFBLElBQ0E7QUFBQSxJQUNBO0FBQUEsRUFDRjtBQUFBLEVBQ0E7QUFBQSxJQUNFLGtCQUFrQjtBQUFBO0FBQUEsTUFFaEI7QUFBQSxRQUNFLE9BQU8sbURBQW1ELGNBQWM7QUFBQSxRQUN4RSxhQUFhO0FBQUEsUUFDYixPQUFPO0FBQUEsUUFDUCxRQUFRO0FBQUEsUUFDUixVQUFVO0FBQUEsTUFDWjtBQUFBLE1BQ0E7QUFBQSxRQUNFLE9BQU8sa0NBQWtDLGFBQWEsSUFBSSxhQUFhO0FBQUEsUUFDdkUsYUFBYTtBQUFBLFFBQ2IsT0FBTztBQUFBLFFBQ1AsUUFBUTtBQUFBLFFBQ1IsVUFBVTtBQUFBLE1BQ1o7QUFBQSxNQUNBO0FBQUEsUUFDRSxPQUFPLG9CQUFvQixjQUFjLElBQUksYUFBYTtB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
