"use client";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { AnimatePresence, motion } from "motion/react";
import { createElement, useCallback, useRef, useState } from "react";
import { useCssVarDims } from "../hooks/use-css-var-dims.js";
import { useGpuTier } from "../hooks/use-gpu-tier.js";
import { cn } from "../utils/index.js";
import { Blink } from "./components/blink.js";
import { Cell, Grid } from "./components/grid/index.js";
import { HoverBg } from "./components/hover-bg.js";
import { HamburgerIcon } from "./components/icons/hamburger.js";
import { Scramble } from "./components/scramble.js";
import { Socials } from "./components/socials.js";
import { ThemeToggle } from "./components/theme-toggle.js";
import { H2 } from "./components/typography/h2.js";
import { Small } from "./components/typography/small.js";
const DEFAULT_BRAND = /* @__PURE__ */ jsxs("hgroup", { className: "flex flex-col gap-2", children: [
  /* @__PURE__ */ jsx(Small, { children: "OpenAmer" }),
  /* @__PURE__ */ jsx(H2, { children: "Research" })
] });
const DEFAULT_LINKS = [
  { href: "/projects", label: "Projects" },
  { href: "/participants", label: "Participants" },
  { href: "/provenance", label: "Provenance" },
  { href: "/contribute", label: "Contribute" }
];
export function Header({
  brand = DEFAULT_BRAND,
  brandHref = "/",
  className,
  desktopGridStyle,
  links = DEFAULT_LINKS,
  LinkComponent = "a",
  scramble: scrambleProp = true,
  socials,
  socialsLabel = "Socials",
  style,
  themeLabel = "Theme",
  themeToggle = false
}) {
  const ref = useRef(null);
  useCssVarDims("header", ref);
  const gpuTier = useGpuTier();
  const scramble = scrambleProp && gpuTier > 0;
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const hasSocials = (socials?.length ?? 0) > 0;
  const hasMobileChrome = themeToggle || hasSocials;
  return /* @__PURE__ */ jsxs("header", { className, ref, style, children: [
    /* @__PURE__ */ jsxs(
      Grid,
      {
        className: "hidden border-t border-b lg:grid",
        style: desktopGridStyle,
        children: [
          /* @__PURE__ */ jsx(
            BrandCell,
            {
              brand,
              href: brandHref,
              LinkComponent
            }
          ),
          links.map((link) => /* @__PURE__ */ jsx(
            NavCell,
            {
              link,
              LinkComponent,
              scramble
            },
            link.href
          )),
          hasSocials && /* @__PURE__ */ jsxs(Cell, { className: "flex items-start justify-between", children: [
            /* @__PURE__ */ jsx(Small, { className: "opacity-50", children: socialsLabel }),
            /* @__PURE__ */ jsx(Socials, { items: socials })
          ] }),
          themeToggle && /* @__PURE__ */ jsxs(Cell, { className: "flex items-start justify-between", children: [
            /* @__PURE__ */ jsx(Small, { className: "opacity-50", children: themeLabel }),
            /* @__PURE__ */ jsx(ThemeToggle, {})
          ] })
        ]
      }
    ),
    /* @__PURE__ */ jsxs(
      "div",
      {
        className: cn(
          "flex items-center justify-between border border-current/20 p-4",
          "lg:hidden"
        ),
        children: [
          /* @__PURE__ */ jsx(
            BrandLink,
            {
              brand,
              href: brandHref,
              LinkComponent
            }
          ),
          /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
            themeToggle && /* @__PURE__ */ jsx(ThemeToggle, {}),
            /* @__PURE__ */ jsx(
              "button",
              {
                "aria-label": open ? "Close menu" : "Open menu",
                className: "relative z-50 cursor-pointer bg-transparent p-2",
                onClick: () => setOpen((v) => !v),
                type: "button",
                children: /* @__PURE__ */ jsx(HamburgerIcon, { open })
              }
            )
          ] })
        ]
      }
    ),
    /* @__PURE__ */ jsx(AnimatePresence, { children: open && /* @__PURE__ */ jsx(
      motion.div,
      {
        animate: { opacity: 1 },
        className: cn(
          "bg-background/95 fixed inset-0 z-50 flex flex-col backdrop-blur-sm",
          "p-8 lg:hidden"
        ),
        exit: { opacity: 0 },
        initial: { opacity: 0 },
        transition: { duration: 0.2 },
        children: /* @__PURE__ */ jsxs("div", { className: "flex flex-col border border-current/20", children: [
          /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between border-b border-current/20 p-4", children: [
            /* @__PURE__ */ jsx(
              BrandLink,
              {
                brand,
                href: brandHref,
                LinkComponent,
                onClick: close
              }
            ),
            /* @__PURE__ */ jsx(
              "button",
              {
                "aria-label": "Close menu",
                className: "cursor-pointer bg-transparent p-2",
                onClick: close,
                type: "button",
                children: /* @__PURE__ */ jsx(HamburgerIcon, { open: true })
              }
            )
          ] }),
          links.map((link) => /* @__PURE__ */ jsx(
            MobileNavLink,
            {
              link,
              LinkComponent,
              onNavigate: close,
              scramble
            },
            link.href
          )),
          hasMobileChrome && /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3 border-b border-current/20 p-4", children: [
            hasSocials && /* @__PURE__ */ jsxs(Fragment, { children: [
              /* @__PURE__ */ jsx(Small, { className: "opacity-50", children: socialsLabel }),
              /* @__PURE__ */ jsx(Socials, { items: socials, onNavigate: close })
            ] }),
            themeToggle && hasSocials && /* @__PURE__ */ jsx("span", { className: "flex-1" }),
            themeToggle && /* @__PURE__ */ jsxs(Fragment, { children: [
              /* @__PURE__ */ jsx(Small, { className: "opacity-50", children: themeLabel }),
              /* @__PURE__ */ jsx(ThemeToggle, {})
            ] })
          ] })
        ] })
      }
    ) })
  ] });
}
function BrandCell({ brand, href, LinkComponent }) {
  return isExternal(href) ? /* @__PURE__ */ jsx(Cell, { href, ...EXTERNAL_REL, as: "a", children: brand }) : /* @__PURE__ */ jsx(Cell, { as: LinkComponent, href, children: brand });
}
function BrandLink({ brand, href, LinkComponent, onClick }) {
  if (isExternal(href)) {
    return /* @__PURE__ */ jsx("a", { href, onClick, ...EXTERNAL_REL, children: brand });
  }
  return createElement(
    LinkComponent,
    { href, onClick },
    brand
  );
}
function NavCell({ link, LinkComponent, scramble }) {
  const ref = useRef(null);
  const isExt = link.external ?? isExternal(link.href);
  const inner = /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsxs(Small, { children: [
      scramble ? /* @__PURE__ */ jsx(Scramble, { target: ref, children: link.label }) : link.label,
      /* @__PURE__ */ jsx(Blink, {})
    ] }),
    /* @__PURE__ */ jsx(HoverBg, {})
  ] });
  if (isExt) {
    return /* @__PURE__ */ jsx(
      Cell,
      {
        as: "a",
        className: "group relative cursor-pointer",
        href: link.href,
        onClick: link.onClick,
        ref,
        ...EXTERNAL_REL,
        children: inner
      }
    );
  }
  return /* @__PURE__ */ jsx(
    Cell,
    {
      as: LinkComponent,
      className: "group relative cursor-pointer",
      href: link.href,
      onClick: link.onClick,
      ref,
      children: inner
    }
  );
}
function MobileNavLink({
  link,
  LinkComponent,
  onNavigate,
  scramble
}) {
  const ref = useRef(null);
  const isExt = link.external ?? isExternal(link.href);
  const className = cn(
    "group relative flex cursor-pointer items-center border-b border-current/20 p-4"
  );
  const onClick = (e) => {
    link.onClick?.(e);
    onNavigate();
  };
  const children = /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsxs(Small, { children: [
      scramble ? /* @__PURE__ */ jsx(Scramble, { target: ref, children: link.label }) : link.label,
      /* @__PURE__ */ jsx(Blink, {})
    ] }),
    /* @__PURE__ */ jsx(HoverBg, {})
  ] });
  if (isExt) {
    return /* @__PURE__ */ jsx(
      "a",
      {
        className,
        href: link.href,
        onClick,
        ref,
        ...EXTERNAL_REL,
        children
      }
    );
  }
  return createElement(
    LinkComponent,
    { className, href: link.href, onClick, ref },
    children
  );
}
const EXTERNAL_REL = {
  rel: "noopener noreferrer",
  target: "_blank"
};
const isExternal = (href) => /^(https?:|mailto:|tel:)/i.test(href);
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IEFuaW1hdGVQcmVzZW5jZSwgbW90aW9uIH0gZnJvbSAnbW90aW9uL3JlYWN0J1xuaW1wb3J0IHsgY3JlYXRlRWxlbWVudCwgdXNlQ2FsbGJhY2ssIHVzZVJlZiwgdXNlU3RhdGUgfSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IHsgdXNlQ3NzVmFyRGltcyB9IGZyb20gJy4uL2hvb2tzL3VzZS1jc3MtdmFyLWRpbXMnXG5pbXBvcnQgeyB1c2VHcHVUaWVyIH0gZnJvbSAnLi4vaG9va3MvdXNlLWdwdS10aWVyJ1xuaW1wb3J0IHsgY24gfSBmcm9tICcuLi91dGlscydcblxuaW1wb3J0IHsgQmxpbmsgfSBmcm9tICcuL2NvbXBvbmVudHMvYmxpbmsnXG5pbXBvcnQgeyBDZWxsLCBHcmlkIH0gZnJvbSAnLi9jb21wb25lbnRzL2dyaWQnXG5pbXBvcnQgeyBIb3ZlckJnIH0gZnJvbSAnLi9jb21wb25lbnRzL2hvdmVyLWJnJ1xuaW1wb3J0IHsgSGFtYnVyZ2VySWNvbiB9IGZyb20gJy4vY29tcG9uZW50cy9pY29ucy9oYW1idXJnZXInXG5pbXBvcnQgeyBTY3JhbWJsZSB9IGZyb20gJy4vY29tcG9uZW50cy9zY3JhbWJsZSdcbmltcG9ydCB7IFNvY2lhbHMsIHR5cGUgU29jaWFsTGluayB9IGZyb20gJy4vY29tcG9uZW50cy9zb2NpYWxzJ1xuaW1wb3J0IHsgVGhlbWVUb2dnbGUgfSBmcm9tICcuL2NvbXBvbmVudHMvdGhlbWUtdG9nZ2xlJ1xuaW1wb3J0IHsgSDIgfSBmcm9tICcuL2NvbXBvbmVudHMvdHlwb2dyYXBoeS9oMidcbmltcG9ydCB7IFNtYWxsIH0gZnJvbSAnLi9jb21wb25lbnRzL3R5cG9ncmFwaHkvc21hbGwnXG5cbmNvbnN0IERFRkFVTFRfQlJBTkQgPSAoXG4gIDxoZ3JvdXAgY2xhc3NOYW1lPVwiZmxleCBmbGV4LWNvbCBnYXAtMlwiPlxuICAgIDxTbWFsbD5Ob3VzPC9TbWFsbD5cblxuICAgIDxIMj5SZXNlYXJjaDwvSDI+XG4gIDwvaGdyb3VwPlxuKVxuXG5jb25zdCBERUZBVUxUX0xJTktTOiBIZWFkZXJMaW5rW10gPSBbXG4gIHsgaHJlZjogJy9wcm9qZWN0cycsIGxhYmVsOiAnUHJvamVjdHMnIH0sXG4gIHsgaHJlZjogJy9wYXJ0aWNpcGFudHMnLCBsYWJlbDogJ1BhcnRpY2lwYW50cycgfSxcbiAgeyBocmVmOiAnL3Byb3ZlbmFuY2UnLCBsYWJlbDogJ1Byb3ZlbmFuY2UnIH0sXG4gIHsgaHJlZjogJy9jb250cmlidXRlJywgbGFiZWw6ICdDb250cmlidXRlJyB9XG5dXG5cbmV4cG9ydCBmdW5jdGlvbiBIZWFkZXIoe1xuICBicmFuZCA9IERFRkFVTFRfQlJBTkQsXG4gIGJyYW5kSHJlZiA9ICcvJyxcbiAgY2xhc3NOYW1lLFxuICBkZXNrdG9wR3JpZFN0eWxlLFxuICBsaW5rcyA9IERFRkFVTFRfTElOS1MsXG4gIExpbmtDb21wb25lbnQgPSAnYScsXG4gIHNjcmFtYmxlOiBzY3JhbWJsZVByb3AgPSB0cnVlLFxuICBzb2NpYWxzLFxuICBzb2NpYWxzTGFiZWwgPSAnU29jaWFscycsXG4gIHN0eWxlLFxuICB0aGVtZUxhYmVsID0gJ1RoZW1lJyxcbiAgdGhlbWVUb2dnbGUgPSBmYWxzZVxufTogSGVhZGVyUHJvcHMpIHtcbiAgY29uc3QgcmVmID0gdXNlUmVmPEhUTUxFbGVtZW50PihudWxsKVxuICB1c2VDc3NWYXJEaW1zKCdoZWFkZXInLCByZWYpXG5cbiAgLy8gU2tpcCB0aGUgaG92ZXItU2NyYW1ibGUgckFGIGxvb3Agb24gdGllci0wIGRldmljZXMgKG5vIEdQVSAvIHNvZnR3YXJlXG4gIC8vIHJlbmRlcmVyIC8gYHByZWZlcnMtcmVkdWNlZC1tb3Rpb246IHJlZHVjZWApIHJlZ2FyZGxlc3Mgb2YgdGhlIHByb3AuXG4gIGNvbnN0IGdwdVRpZXIgPSB1c2VHcHVUaWVyKClcbiAgY29uc3Qgc2NyYW1ibGUgPSBzY3JhbWJsZVByb3AgJiYgZ3B1VGllciA+IDBcblxuICBjb25zdCBbb3Blbiwgc2V0T3Blbl0gPSB1c2VTdGF0ZShmYWxzZSlcbiAgY29uc3QgY2xvc2UgPSB1c2VDYWxsYmFjaygoKSA9PiBzZXRPcGVuKGZhbHNlKSwgW10pXG5cbiAgY29uc3QgaGFzU29jaWFscyA9IChzb2NpYWxzPy5sZW5ndGggPz8gMCkgPiAwXG4gIGNvbnN0IGhhc01vYmlsZUNocm9tZSA9IHRoZW1lVG9nZ2xlIHx8IGhhc1NvY2lhbHNcblxuICByZXR1cm4gKFxuICAgIDxoZWFkZXIgY2xhc3NOYW1lPXtjbGFzc05hbWV9IHJlZj17cmVmfSBzdHlsZT17c3R5bGV9PlxuICAgICAgPEdyaWRcbiAgICAgICAgY2xhc3NOYW1lPVwiaGlkZGVuIGJvcmRlci10IGJvcmRlci1iIGxnOmdyaWRcIlxuICAgICAgICBzdHlsZT17ZGVza3RvcEdyaWRTdHlsZX1cbiAgICAgID5cbiAgICAgICAgPEJyYW5kQ2VsbFxuICAgICAgICAgIGJyYW5kPXticmFuZH1cbiAgICAgICAgICBocmVmPXticmFuZEhyZWZ9XG4gICAgICAgICAgTGlua0NvbXBvbmVudD17TGlua0NvbXBvbmVudH1cbiAgICAgICAgLz5cblxuICAgICAgICB7bGlua3MubWFwKGxpbmsgPT4gKFxuICAgICAgICAgIDxOYXZDZWxsXG4gICAgICAgICAgICBrZXk9e2xpbmsuaHJlZn1cbiAgICAgICAgICAgIGxpbms9e2xpbmt9XG4gICAgICAgICAgICBMaW5rQ29tcG9uZW50PXtMaW5rQ29tcG9uZW50fVxuICAgICAgICAgICAgc2NyYW1ibGU9e3NjcmFtYmxlfVxuICAgICAgICAgIC8+XG4gICAgICAgICkpfVxuXG4gICAgICAgIHtoYXNTb2NpYWxzICYmIChcbiAgICAgICAgICA8Q2VsbCBjbGFzc05hbWU9XCJmbGV4IGl0ZW1zLXN0YXJ0IGp1c3RpZnktYmV0d2VlblwiPlxuICAgICAgICAgICAgPFNtYWxsIGNsYXNzTmFtZT1cIm9wYWNpdHktNTBcIj57c29jaWFsc0xhYmVsfTwvU21hbGw+XG5cbiAgICAgICAgICAgIDxTb2NpYWxzIGl0ZW1zPXtzb2NpYWxzIX0gLz5cbiAgICAgICAgICA8L0NlbGw+XG4gICAgICAgICl9XG5cbiAgICAgICAge3RoZW1lVG9nZ2xlICYmIChcbiAgICAgICAgICA8Q2VsbCBjbGFzc05hbWU9XCJmbGV4IGl0ZW1zLXN0YXJ0IGp1c3RpZnktYmV0d2VlblwiPlxuICAgICAgICAgICAgPFNtYWxsIGNsYXNzTmFtZT1cIm9wYWNpdHktNTBcIj57dGhlbWVMYWJlbH08L1NtYWxsPlxuXG4gICAgICAgICAgICA8VGhlbWVUb2dnbGUgLz5cbiAgICAgICAgICA8L0NlbGw+XG4gICAgICAgICl9XG4gICAgICA8L0dyaWQ+XG5cbiAgICAgIDxkaXZcbiAgICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgICAnZmxleCBpdGVtcy1jZW50ZXIganVzdGlmeS1iZXR3ZWVuIGJvcmRlciBib3JkZXItY3VycmVudC8yMCBwLTQnLFxuICAgICAgICAgICdsZzpoaWRkZW4nXG4gICAgICAgICl9XG4gICAgICA+XG4gICAgICAgIDxCcmFuZExpbmtcbiAgICAgICAgICBicmFuZD17YnJhbmR9XG4gICAgICAgICAgaHJlZj17YnJhbmRIcmVmfVxuICAgICAgICAgIExpbmtDb21wb25lbnQ9e0xpbmtDb21wb25lbnR9XG4gICAgICAgIC8+XG5cbiAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGl0ZW1zLWNlbnRlciBnYXAtM1wiPlxuICAgICAgICAgIHt0aGVtZVRvZ2dsZSAmJiA8VGhlbWVUb2dnbGUgLz59XG5cbiAgICAgICAgICA8YnV0dG9uXG4gICAgICAgICAgICBhcmlhLWxhYmVsPXtvcGVuID8gJ0Nsb3NlIG1lbnUnIDogJ09wZW4gbWVudSd9XG4gICAgICAgICAgICBjbGFzc05hbWU9XCJyZWxhdGl2ZSB6LTUwIGN1cnNvci1wb2ludGVyIGJnLXRyYW5zcGFyZW50IHAtMlwiXG4gICAgICAgICAgICBvbkNsaWNrPXsoKSA9PiBzZXRPcGVuKHYgPT4gIXYpfVxuICAgICAgICAgICAgdHlwZT1cImJ1dHRvblwiXG4gICAgICAgICAgPlxuICAgICAgICAgICAgPEhhbWJ1cmdlckljb24gb3Blbj17b3Blbn0gLz5cbiAgICAgICAgICA8L2J1dHRvbj5cbiAgICAgICAgPC9kaXY+XG4gICAgICA8L2Rpdj5cblxuICAgICAgPEFuaW1hdGVQcmVzZW5jZT5cbiAgICAgICAge29wZW4gJiYgKFxuICAgICAgICAgIDxtb3Rpb24uZGl2XG4gICAgICAgICAgICBhbmltYXRlPXt7IG9wYWNpdHk6IDEgfX1cbiAgICAgICAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICAgICAgICdiZy1iYWNrZ3JvdW5kLzk1IGZpeGVkIGluc2V0LTAgei01MCBmbGV4IGZsZXgtY29sIGJhY2tkcm9wLWJsdXItc20nLFxuICAgICAgICAgICAgICAncC04IGxnOmhpZGRlbidcbiAgICAgICAgICAgICl9XG4gICAgICAgICAgICBleGl0PXt7IG9wYWNpdHk6IDAgfX1cbiAgICAgICAgICAgIGluaXRpYWw9e3sgb3BhY2l0eTogMCB9fVxuICAgICAgICAgICAgdHJhbnNpdGlvbj17eyBkdXJhdGlvbjogMC4yIH19XG4gICAgICAgICAgPlxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGZsZXgtY29sIGJvcmRlciBib3JkZXItY3VycmVudC8yMFwiPlxuICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImZsZXggaXRlbXMtY2VudGVyIGp1c3RpZnktYmV0d2VlbiBib3JkZXItYiBib3JkZXItY3VycmVudC8yMCBwLTRcIj5cbiAgICAgICAgICAgICAgICA8QnJhbmRMaW5rXG4gICAgICAgICAgICAgICAgICBicmFuZD17YnJhbmR9XG4gICAgICAgICAgICAgICAgICBocmVmPXticmFuZEhyZWZ9XG4gICAgICAgICAgICAgICAgICBMaW5rQ29tcG9uZW50PXtMaW5rQ29tcG9uZW50fVxuICAgICAgICAgICAgICAgICAgb25DbGljaz17Y2xvc2V9XG4gICAgICAgICAgICAgICAgLz5cblxuICAgICAgICAgICAgICAgIDxidXR0b25cbiAgICAgICAgICAgICAgICAgIGFyaWEtbGFiZWw9XCJDbG9zZSBtZW51XCJcbiAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cImN1cnNvci1wb2ludGVyIGJnLXRyYW5zcGFyZW50IHAtMlwiXG4gICAgICAgICAgICAgICAgICBvbkNsaWNrPXtjbG9zZX1cbiAgICAgICAgICAgICAgICAgIHR5cGU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgID5cbiAgICAgICAgICAgICAgICAgIDxIYW1idXJnZXJJY29uIG9wZW4gLz5cbiAgICAgICAgICAgICAgICA8L2J1dHRvbj5cbiAgICAgICAgICAgICAgPC9kaXY+XG5cbiAgICAgICAgICAgICAge2xpbmtzLm1hcChsaW5rID0+IChcbiAgICAgICAgICAgICAgICA8TW9iaWxlTmF2TGlua1xuICAgICAgICAgICAgICAgICAga2V5PXtsaW5rLmhyZWZ9XG4gICAgICAgICAgICAgICAgICBsaW5rPXtsaW5rfVxuICAgICAgICAgICAgICAgICAgTGlua0NvbXBvbmVudD17TGlua0NvbXBvbmVudH1cbiAgICAgICAgICAgICAgICAgIG9uTmF2aWdhdGU9e2Nsb3NlfVxuICAgICAgICAgICAgICAgICAgc2NyYW1ibGU9e3NjcmFtYmxlfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICkpfVxuXG4gICAgICAgICAgICAgIHtoYXNNb2JpbGVDaHJvbWUgJiYgKFxuICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBpdGVtcy1jZW50ZXIgZ2FwLTMgYm9yZGVyLWIgYm9yZGVyLWN1cnJlbnQvMjAgcC00XCI+XG4gICAgICAgICAgICAgICAgICB7aGFzU29jaWFscyAmJiAoXG4gICAgICAgICAgICAgICAgICAgIDw+XG4gICAgICAgICAgICAgICAgICAgICAgPFNtYWxsIGNsYXNzTmFtZT1cIm9wYWNpdHktNTBcIj57c29jaWFsc0xhYmVsfTwvU21hbGw+XG5cbiAgICAgICAgICAgICAgICAgICAgICA8U29jaWFscyBpdGVtcz17c29jaWFscyF9IG9uTmF2aWdhdGU9e2Nsb3NlfSAvPlxuICAgICAgICAgICAgICAgICAgICA8Lz5cbiAgICAgICAgICAgICAgICAgICl9XG5cbiAgICAgICAgICAgICAgICAgIHt0aGVtZVRvZ2dsZSAmJiBoYXNTb2NpYWxzICYmIDxzcGFuIGNsYXNzTmFtZT1cImZsZXgtMVwiIC8+fVxuXG4gICAgICAgICAgICAgICAgICB7dGhlbWVUb2dnbGUgJiYgKFxuICAgICAgICAgICAgICAgICAgICA8PlxuICAgICAgICAgICAgICAgICAgICAgIDxTbWFsbCBjbGFzc05hbWU9XCJvcGFjaXR5LTUwXCI+e3RoZW1lTGFiZWx9PC9TbWFsbD5cblxuICAgICAgICAgICAgICAgICAgICAgIDxUaGVtZVRvZ2dsZSAvPlxuICAgICAgICAgICAgICAgICAgICA8Lz5cbiAgICAgICAgICAgICAgICAgICl9XG4gICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICl9XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICA8L21vdGlvbi5kaXY+XG4gICAgICAgICl9XG4gICAgICA8L0FuaW1hdGVQcmVzZW5jZT5cbiAgICA8L2hlYWRlcj5cbiAgKVxufVxuXG5mdW5jdGlvbiBCcmFuZENlbGwoeyBicmFuZCwgaHJlZiwgTGlua0NvbXBvbmVudCB9OiBCcmFuZFNsb3RQcm9wcykge1xuICByZXR1cm4gaXNFeHRlcm5hbChocmVmKSA/IChcbiAgICA8Q2VsbCBocmVmPXtocmVmfSB7Li4uRVhURVJOQUxfUkVMfSBhcz1cImFcIj5cbiAgICAgIHticmFuZH1cbiAgICA8L0NlbGw+XG4gICkgOiAoXG4gICAgPENlbGwgYXM9e0xpbmtDb21wb25lbnR9IGhyZWY9e2hyZWZ9PlxuICAgICAge2JyYW5kfVxuICAgIDwvQ2VsbD5cbiAgKVxufVxuXG5mdW5jdGlvbiBCcmFuZExpbmsoeyBicmFuZCwgaHJlZiwgTGlua0NvbXBvbmVudCwgb25DbGljayB9OiBCcmFuZExpbmtQcm9wcykge1xuICBpZiAoaXNFeHRlcm5hbChocmVmKSkge1xuICAgIHJldHVybiAoXG4gICAgICA8YSBocmVmPXtocmVmfSBvbkNsaWNrPXtvbkNsaWNrfSB7Li4uRVhURVJOQUxfUkVMfT5cbiAgICAgICAge2JyYW5kfVxuICAgICAgPC9hPlxuICAgIClcbiAgfVxuXG4gIHJldHVybiBjcmVhdGVFbGVtZW50KFxuICAgIExpbmtDb21wb25lbnQsXG4gICAgeyBocmVmLCBvbkNsaWNrIH0gYXMgUmVjb3JkPHN0cmluZywgdW5rbm93bj4sXG4gICAgYnJhbmRcbiAgKVxufVxuXG5mdW5jdGlvbiBOYXZDZWxsKHsgbGluaywgTGlua0NvbXBvbmVudCwgc2NyYW1ibGUgfTogTmF2Q2VsbFByb3BzKSB7XG4gIGNvbnN0IHJlZiA9IHVzZVJlZjxIVE1MQW5jaG9yRWxlbWVudD4obnVsbClcbiAgY29uc3QgaXNFeHQgPSBsaW5rLmV4dGVybmFsID8/IGlzRXh0ZXJuYWwobGluay5ocmVmKVxuXG4gIGNvbnN0IGlubmVyID0gKFxuICAgIDw+XG4gICAgICA8U21hbGw+XG4gICAgICAgIHtzY3JhbWJsZSA/IChcbiAgICAgICAgICA8U2NyYW1ibGUgdGFyZ2V0PXtyZWZ9PntsaW5rLmxhYmVsfTwvU2NyYW1ibGU+XG4gICAgICAgICkgOiAoXG4gICAgICAgICAgbGluay5sYWJlbFxuICAgICAgICApfVxuXG4gICAgICAgIDxCbGluayAvPlxuICAgICAgPC9TbWFsbD5cblxuICAgICAgPEhvdmVyQmcgLz5cbiAgICA8Lz5cbiAgKVxuXG4gIGlmIChpc0V4dCkge1xuICAgIHJldHVybiAoXG4gICAgICA8Q2VsbFxuICAgICAgICBhcz1cImFcIlxuICAgICAgICBjbGFzc05hbWU9XCJncm91cCByZWxhdGl2ZSBjdXJzb3ItcG9pbnRlclwiXG4gICAgICAgIGhyZWY9e2xpbmsuaHJlZn1cbiAgICAgICAgb25DbGljaz17bGluay5vbkNsaWNrfVxuICAgICAgICByZWY9e3JlZn1cbiAgICAgICAgey4uLkVYVEVSTkFMX1JFTH1cbiAgICAgID5cbiAgICAgICAge2lubmVyfVxuICAgICAgPC9DZWxsPlxuICAgIClcbiAgfVxuXG4gIHJldHVybiAoXG4gICAgPENlbGxcbiAgICAgIGFzPXtMaW5rQ29tcG9uZW50fVxuICAgICAgY2xhc3NOYW1lPVwiZ3JvdXAgcmVsYXRpdmUgY3Vyc29yLXBvaW50ZXJcIlxuICAgICAgaHJlZj17bGluay5ocmVmfVxuICAgICAgb25DbGljaz17bGluay5vbkNsaWNrfVxuICAgICAgcmVmPXtyZWZ9XG4gICAgPlxuICAgICAge2lubmVyfVxuICAgIDwvQ2VsbD5cbiAgKVxufVxuXG5mdW5jdGlvbiBNb2JpbGVOYXZMaW5rKHtcbiAgbGluayxcbiAgTGlua0NvbXBvbmVudCxcbiAgb25OYXZpZ2F0ZSxcbiAgc2NyYW1ibGVcbn06IE1vYmlsZU5hdkxpbmtQcm9wcykge1xuICBjb25zdCByZWYgPSB1c2VSZWY8SFRNTEFuY2hvckVsZW1lbnQ+KG51bGwpXG4gIGNvbnN0IGlzRXh0ID0gbGluay5leHRlcm5hbCA/PyBpc0V4dGVybmFsKGxpbmsuaHJlZilcblxuICBjb25zdCBjbGFzc05hbWUgPSBjbihcbiAgICAnZ3JvdXAgcmVsYXRpdmUgZmxleCBjdXJzb3ItcG9pbnRlciBpdGVtcy1jZW50ZXIgYm9yZGVyLWIgYm9yZGVyLWN1cnJlbnQvMjAgcC00J1xuICApXG5cbiAgY29uc3Qgb25DbGljayA9IChlOiBSZWFjdC5Nb3VzZUV2ZW50PEhUTUxBbmNob3JFbGVtZW50PikgPT4ge1xuICAgIGxpbmsub25DbGljaz8uKGUpXG4gICAgb25OYXZpZ2F0ZSgpXG4gIH1cblxuICBjb25zdCBjaGlsZHJlbiA9IChcbiAgICA8PlxuICAgICAgPFNtYWxsPlxuICAgICAgICB7c2NyYW1ibGUgPyAoXG4gICAgICAgICAgPFNjcmFtYmxlIHRhcmdldD17cmVmfT57bGluay5sYWJlbH08L1NjcmFtYmxlPlxuICAgICAgICApIDogKFxuICAgICAgICAgIGxpbmsubGFiZWxcbiAgICAgICAgKX1cblxuICAgICAgICA8QmxpbmsgLz5cbiAgICAgIDwvU21hbGw+XG5cbiAgICAgIDxIb3ZlckJnIC8+XG4gICAgPC8+XG4gIClcblxuICBpZiAoaXNFeHQpIHtcbiAgICByZXR1cm4gKFxuICAgICAgPGFcbiAgICAgICAgY2xhc3NOYW1lPXtjbGFzc05hbWV9XG4gICAgICAgIGhyZWY9e2xpbmsuaHJlZn1cbiAgICAgICAgb25DbGljaz17b25DbGlja31cbiAgICAgICAgcmVmPXtyZWZ9XG4gICAgICAgIHsuLi5FWFRFUk5BTF9SRUx9XG4gICAgICA+XG4gICAgICAgIHtjaGlsZHJlbn1cbiAgICAgIDwvYT5cbiAgICApXG4gIH1cblxuICByZXR1cm4gY3JlYXRlRWxlbWVudChcbiAgICBMaW5rQ29tcG9uZW50LFxuICAgIHsgY2xhc3NOYW1lLCBocmVmOiBsaW5rLmhyZWYsIG9uQ2xpY2ssIHJlZiB9IGFzIFJlY29yZDxzdHJpbmcsIHVua25vd24+LFxuICAgIGNoaWxkcmVuXG4gIClcbn1cblxuY29uc3QgRVhURVJOQUxfUkVMID0ge1xuICByZWw6ICdub29wZW5lciBub3JlZmVycmVyJyxcbiAgdGFyZ2V0OiAnX2JsYW5rJ1xufSBhcyBjb25zdFxuXG5jb25zdCBpc0V4dGVybmFsID0gKGhyZWY6IHN0cmluZykgPT4gL14oaHR0cHM/OnxtYWlsdG86fHRlbDopL2kudGVzdChocmVmKVxuXG5pbnRlcmZhY2UgQnJhbmRMaW5rUHJvcHMgZXh0ZW5kcyBCcmFuZFNsb3RQcm9wcyB7XG4gIG9uQ2xpY2s/OiBSZWFjdC5Nb3VzZUV2ZW50SGFuZGxlclxufVxuXG5pbnRlcmZhY2UgQnJhbmRTbG90UHJvcHMge1xuICBicmFuZDogUmVhY3QuUmVhY3ROb2RlXG4gIGhyZWY6IHN0cmluZ1xuICBMaW5rQ29tcG9uZW50OiBSZWFjdC5FbGVtZW50VHlwZVxufVxuXG5leHBvcnQgaW50ZXJmYWNlIEhlYWRlckxpbmsge1xuICBleHRlcm5hbD86IGJvb2xlYW5cbiAgaHJlZjogc3RyaW5nXG4gIGxhYmVsOiBzdHJpbmdcbiAgb25DbGljaz86IFJlYWN0Lk1vdXNlRXZlbnRIYW5kbGVyXG59XG5cbmV4cG9ydCBpbnRlcmZhY2UgSGVhZGVyUHJvcHMge1xuICBicmFuZD86IFJlYWN0LlJlYWN0Tm9kZVxuICBicmFuZEhyZWY/OiBzdHJpbmdcbiAgY2xhc3NOYW1lPzogc3RyaW5nXG4gIC8qKlxuICAgKiBJbmxpbmUgYHN0eWxlYCBmb3IgdGhlIGRlc2t0b3AgYEdyaWRgIG9ubHkgXHUyMDE0IHVzZWZ1bCBmb3Igb3ZlcnJpZGluZ1xuICAgKiBgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zYCAoZS5nLiB0byBhbGlnbiB3aXRoIGEgc2lkZWJhciB0cmFjaykgd2l0aG91dFxuICAgKiBhZmZlY3RpbmcgdGhlIG1vYmlsZSBiYXIgb3IgZHJhd2VyLlxuICAgKi9cbiAgZGVza3RvcEdyaWRTdHlsZT86IFJlYWN0LkNTU1Byb3BlcnRpZXNcbiAgbGlua3M/OiBIZWFkZXJMaW5rW11cbiAgTGlua0NvbXBvbmVudD86IFJlYWN0LkVsZW1lbnRUeXBlXG4gIC8qKlxuICAgKiBBcHBseSB0aGUgaG92ZXItU2NyYW1ibGUgZWZmZWN0IHRvIG5hdiBsaW5rIGxhYmVscy4gRGVmYXVsdHMgdG8gYHRydWVgLFxuICAgKiBhdXRvbWF0aWNhbGx5IHN1cHByZXNzZWQgb24gdGllci0wIEdQVXMgYW5kIHdoZW4gdGhlIHVzZXIgaGFzXG4gICAqIGBwcmVmZXJzLXJlZHVjZWQtbW90aW9uOiByZWR1Y2VgLlxuICAgKi9cbiAgc2NyYW1ibGU/OiBib29sZWFuXG4gIC8qKlxuICAgKiBPcHRpb25hbCBzb2NpYWxzIHNob3duIGluIGEgdHJhaWxpbmcgY2hyb21lIGNlbGwgb24gZGVza3RvcCBhbmQgaW4gdGhlXG4gICAqIG1vYmlsZSBkcmF3ZXIncyBjaHJvbWUgcm93LiBGb3IgbmF2LWhlYXZ5IHByb2R1Y3RzIChcdTIyNjUgNSBsaW5rcykgcHJlZmVyXG4gICAqIHBhc3Npbmcgc29jaWFscyB0byBgPEZvb3Rlcj5gIGluc3RlYWQgXHUyMDE0IHRoZSBkZXNrdG9wIGBHcmlkYCBvbmx5IHNoaXBzXG4gICAqIGNvbHVtbiBydWxlcyB0aHJvdWdoIGBncmlkLWNvbHMtNmAsIHNvIGJyYW5kICsgbWFueSBsaW5rcyArIGNocm9tZSBjYW5cbiAgICogb3ZlcmZsb3cuXG4gICAqL1xuICBzb2NpYWxzPzogU29jaWFsTGlua1tdXG4gIHNvY2lhbHNMYWJlbD86IHN0cmluZ1xuICBzdHlsZT86IFJlYWN0LkNTU1Byb3BlcnRpZXNcbiAgdGhlbWVMYWJlbD86IHN0cmluZ1xuICB0aGVtZVRvZ2dsZT86IGJvb2xlYW5cbn1cblxuLyoqIEBkZXByZWNhdGVkIFVzZSBgU29jaWFsTGlua2AgZnJvbSBgQG5vdXMtcmVzZWFyY2gvdWlgLiBTYW1lIHNoYXBlLiAqL1xuZXhwb3J0IHR5cGUgSGVhZGVyU29jaWFsID0gU29jaWFsTGlua1xuXG5pbnRlcmZhY2UgTW9iaWxlTmF2TGlua1Byb3BzIHtcbiAgbGluazogSGVhZGVyTGlua1xuICBMaW5rQ29tcG9uZW50OiBSZWFjdC5FbGVtZW50VHlwZVxuICBvbk5hdmlnYXRlOiAoKSA9PiB2b2lkXG4gIHNjcmFtYmxlOiBib29sZWFuXG59XG5cbmludGVyZmFjZSBOYXZDZWxsUHJvcHMge1xuICBsaW5rOiBIZWFkZXJMaW5rXG4gIExpbmtDb21wb25lbnQ6IFJlYWN0LkVsZW1lbnRUeXBlXG4gIHNjcmFtYmxlOiBib29sZWFuXG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBb0JFLFNBc0prQixVQXJKaEIsS0FERjtBQWxCRixTQUFTLGlCQUFpQixjQUFjO0FBQ3hDLFNBQVMsZUFBZSxhQUFhLFFBQVEsZ0JBQWdCO0FBRTdELFNBQVMscUJBQXFCO0FBQzlCLFNBQVMsa0JBQWtCO0FBQzNCLFNBQVMsVUFBVTtBQUVuQixTQUFTLGFBQWE7QUFDdEIsU0FBUyxNQUFNLFlBQVk7QUFDM0IsU0FBUyxlQUFlO0FBQ3hCLFNBQVMscUJBQXFCO0FBQzlCLFNBQVMsZ0JBQWdCO0FBQ3pCLFNBQVMs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
