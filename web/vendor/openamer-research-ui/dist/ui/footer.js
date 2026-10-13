"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import { useRef } from "react";
import { useCssVarDims } from "../hooks/use-css-var-dims.js";
import { Cell, Grid } from "./components/grid/index.js";
import { Socials } from "./components/socials.js";
import { ThemeToggle } from "./components/theme-toggle.js";
import { Small } from "./components/typography/small.js";
const DEFAULT_GROUPS = [
  { label: "Product", links: ["Overview", "Features", "Pricing"] },
  { label: "Resources", links: ["Docs", "Blog", "Support"] },
  { label: "Company", links: ["About", "Careers", "Contact"] },
  { label: "Legal", links: ["Privacy", "Terms", "License"] }
];
export function Footer({
  className,
  groups = DEFAULT_GROUPS,
  LinkComponent = "a",
  socials,
  socialsLabel = "Socials",
  style,
  themeLabel = "Theme",
  themeToggle = false
}) {
  const ref = useRef(null);
  useCssVarDims("footer", ref);
  const hasSocials = (socials?.length ?? 0) > 0;
  const hasChrome = hasSocials || themeToggle;
  return /* @__PURE__ */ jsxs("footer", { className, ref, style, children: [
    /* @__PURE__ */ jsxs(Grid, { children: [
      /* @__PURE__ */ jsx(Cell, { children: /* @__PURE__ */ jsxs(Small, { className: "opacity-50", children: [
        "\xA9",
        (/* @__PURE__ */ new Date()).getFullYear()
      ] }) }),
      groups.map(({ label, links }) => /* @__PURE__ */ jsxs(Cell, { children: [
        /* @__PURE__ */ jsx(Small, { className: "opacity-50", children: label }),
        /* @__PURE__ */ jsx("nav", { className: "mt-3 flex flex-col gap-2", children: links.map((link) => {
          const href = typeof link === "string" ? `/${link.toLowerCase()}` : link.href;
          const label2 = typeof link === "string" ? link : link.label;
          return /* @__PURE__ */ jsx(
            Small,
            {
              as: LinkComponent,
              className: "underline",
              href,
              children: label2
            },
            label2
          );
        }) })
      ] }, label))
    ] }),
    hasChrome && /* @__PURE__ */ jsxs(Grid, { children: [
      hasSocials && /* @__PURE__ */ jsxs(Cell, { className: "flex items-start justify-between", children: [
        /* @__PURE__ */ jsx(Small, { className: "opacity-50", children: socialsLabel }),
        /* @__PURE__ */ jsx(Socials, { items: socials })
      ] }),
      themeToggle && /* @__PURE__ */ jsxs(Cell, { className: "flex items-start justify-between", children: [
        /* @__PURE__ */ jsx(Small, { className: "opacity-50", children: themeLabel }),
        /* @__PURE__ */ jsx(ThemeToggle, {})
      ] })
    ] })
  ] });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZVJlZiB9IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyB1c2VDc3NWYXJEaW1zIH0gZnJvbSAnLi4vaG9va3MvdXNlLWNzcy12YXItZGltcydcbmltcG9ydCB7IENlbGwsIEdyaWQgfSBmcm9tICcuL2NvbXBvbmVudHMvZ3JpZCdcbmltcG9ydCB7IFNvY2lhbHMsIHR5cGUgU29jaWFsTGluayB9IGZyb20gJy4vY29tcG9uZW50cy9zb2NpYWxzJ1xuaW1wb3J0IHsgVGhlbWVUb2dnbGUgfSBmcm9tICcuL2NvbXBvbmVudHMvdGhlbWUtdG9nZ2xlJ1xuaW1wb3J0IHsgU21hbGwgfSBmcm9tICcuL2NvbXBvbmVudHMvdHlwb2dyYXBoeS9zbWFsbCdcblxuY29uc3QgREVGQVVMVF9HUk9VUFM6IEZvb3Rlckdyb3VwW10gPSBbXG4gIHsgbGFiZWw6ICdQcm9kdWN0JywgbGlua3M6IFsnT3ZlcnZpZXcnLCAnRmVhdHVyZXMnLCAnUHJpY2luZyddIH0sXG4gIHsgbGFiZWw6ICdSZXNvdXJjZXMnLCBsaW5rczogWydEb2NzJywgJ0Jsb2cnLCAnU3VwcG9ydCddIH0sXG4gIHsgbGFiZWw6ICdDb21wYW55JywgbGlua3M6IFsnQWJvdXQnLCAnQ2FyZWVycycsICdDb250YWN0J10gfSxcbiAgeyBsYWJlbDogJ0xlZ2FsJywgbGlua3M6IFsnUHJpdmFjeScsICdUZXJtcycsICdMaWNlbnNlJ10gfVxuXVxuXG5leHBvcnQgZnVuY3Rpb24gRm9vdGVyKHtcbiAgY2xhc3NOYW1lLFxuICBncm91cHMgPSBERUZBVUxUX0dST1VQUyxcbiAgTGlua0NvbXBvbmVudCA9ICdhJyxcbiAgc29jaWFscyxcbiAgc29jaWFsc0xhYmVsID0gJ1NvY2lhbHMnLFxuICBzdHlsZSxcbiAgdGhlbWVMYWJlbCA9ICdUaGVtZScsXG4gIHRoZW1lVG9nZ2xlID0gZmFsc2Vcbn06IEZvb3RlclByb3BzKSB7XG4gIGNvbnN0IHJlZiA9IHVzZVJlZjxIVE1MRWxlbWVudD4obnVsbClcbiAgdXNlQ3NzVmFyRGltcygnZm9vdGVyJywgcmVmKVxuXG4gIGNvbnN0IGhhc1NvY2lhbHMgPSAoc29jaWFscz8ubGVuZ3RoID8/IDApID4gMFxuICBjb25zdCBoYXNDaHJvbWUgPSBoYXNTb2NpYWxzIHx8IHRoZW1lVG9nZ2xlXG5cbiAgcmV0dXJuIChcbiAgICA8Zm9vdGVyIGNsYXNzTmFtZT17Y2xhc3NOYW1lfSByZWY9e3JlZn0gc3R5bGU9e3N0eWxlfT5cbiAgICAgIDxHcmlkPlxuICAgICAgICA8Q2VsbD5cbiAgICAgICAgICA8U21hbGwgY2xhc3NOYW1lPVwib3BhY2l0eS01MFwiPiZjb3B5O3tuZXcgRGF0ZSgpLmdldEZ1bGxZZWFyKCl9PC9TbWFsbD5cbiAgICAgICAgPC9DZWxsPlxuXG4gICAgICAgIHtncm91cHMubWFwKCh7IGxhYmVsLCBsaW5rcyB9KSA9PiAoXG4gICAgICAgICAgPENlbGwga2V5PXtsYWJlbH0+XG4gICAgICAgICAgICA8U21hbGwgY2xhc3NOYW1lPVwib3BhY2l0eS01MFwiPntsYWJlbH08L1NtYWxsPlxuXG4gICAgICAgICAgICA8bmF2IGNsYXNzTmFtZT1cIm10LTMgZmxleCBmbGV4LWNvbCBnYXAtMlwiPlxuICAgICAgICAgICAgICB7bGlua3MubWFwKGxpbmsgPT4ge1xuICAgICAgICAgICAgICAgIGNvbnN0IGhyZWYgPSB0eXBlb2YgbGluayA9PT0gJ3N0cmluZydcbiAgICAgICAgICAgICAgICAgID8gYC8ke2xpbmsudG9Mb3dlckNhc2UoKX1gXG4gICAgICAgICAgICAgICAgICA6IGxpbmsuaHJlZlxuXG4gICAgICAgICAgICAgICAgY29uc3QgbGFiZWwgPSB0eXBlb2YgbGluayA9PT0gJ3N0cmluZycgPyBsaW5rIDogbGluay5sYWJlbFxuXG4gICAgICAgICAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgICAgICAgIDxTbWFsbFxuICAgICAgICAgICAgICAgICAgICBhcz17TGlua0NvbXBvbmVudH1cbiAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwidW5kZXJsaW5lXCJcbiAgICAgICAgICAgICAgICAgICAgaHJlZj17aHJlZn1cbiAgICAgICAgICAgICAgICAgICAga2V5PXtsYWJlbH1cbiAgICAgICAgICAgICAgICAgID5cbiAgICAgICAgICAgICAgICAgICAge2xhYmVsfVxuICAgICAgICAgICAgICAgICAgPC9TbWFsbD5cbiAgICAgICAgICAgICAgICApXG4gICAgICAgICAgICAgIH0pfVxuICAgICAgICAgICAgPC9uYXY+XG4gICAgICAgICAgPC9DZWxsPlxuICAgICAgICApKX1cbiAgICAgIDwvR3JpZD5cblxuICAgICAge2hhc0Nocm9tZSAmJiAoXG4gICAgICAgIDxHcmlkPlxuICAgICAgICAgIHtoYXNTb2NpYWxzICYmIChcbiAgICAgICAgICAgIDxDZWxsIGNsYXNzTmFtZT1cImZsZXggaXRlbXMtc3RhcnQganVzdGlmeS1iZXR3ZWVuXCI+XG4gICAgICAgICAgICAgIDxTbWFsbCBjbGFzc05hbWU9XCJvcGFjaXR5LTUwXCI+e3NvY2lhbHNMYWJlbH08L1NtYWxsPlxuXG4gICAgICAgICAgICAgIDxTb2NpYWxzIGl0ZW1zPXtzb2NpYWxzIX0gLz5cbiAgICAgICAgICAgIDwvQ2VsbD5cbiAgICAgICAgICApfVxuXG4gICAgICAgICAge3RoZW1lVG9nZ2xlICYmIChcbiAgICAgICAgICAgIDxDZWxsIGNsYXNzTmFtZT1cImZsZXggaXRlbXMtc3RhcnQganVzdGlmeS1iZXR3ZWVuXCI+XG4gICAgICAgICAgICAgIDxTbWFsbCBjbGFzc05hbWU9XCJvcGFjaXR5LTUwXCI+e3RoZW1lTGFiZWx9PC9TbWFsbD5cblxuICAgICAgICAgICAgICA8VGhlbWVUb2dnbGUgLz5cbiAgICAgICAgICAgIDwvQ2VsbD5cbiAgICAgICAgICApfVxuICAgICAgICA8L0dyaWQ+XG4gICAgICApfVxuICAgIDwvZm9vdGVyPlxuICApXG59XG5cbmV4cG9ydCBpbnRlcmZhY2UgRm9vdGVyR3JvdXAge1xuICBsYWJlbDogc3RyaW5nXG4gIGxpbmtzOiAoRm9vdGVyTGluayB8IHN0cmluZylbXVxufVxuXG5leHBvcnQgaW50ZXJmYWNlIEZvb3Rlckxpbmsge1xuICBocmVmOiBzdHJpbmdcbiAgbGFiZWw6IHN0cmluZ1xufVxuXG5leHBvcnQgaW50ZXJmYWNlIEZvb3RlclByb3BzIHtcbiAgY2xhc3NOYW1lPzogc3RyaW5nXG4gIGdyb3Vwcz86IEZvb3Rlckdyb3VwW11cbiAgTGlua0NvbXBvbmVudD86IFJlYWN0LkVsZW1lbnRUeXBlXG4gIHNvY2lhbHM/OiBTb2NpYWxMaW5rW11cbiAgc29jaWFsc0xhYmVsPzogc3RyaW5nXG4gIHN0eWxlPzogUmVhY3QuQ1NTUHJvcGVydGllc1xuICB0aGVtZUxhYmVsPzogc3RyaW5nXG4gIHRoZW1lVG9nZ2xlPzogYm9vbGVhblxufVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQW9DUSxjQUNFLFlBREY7QUFsQ1IsU0FBUyxjQUFjO0FBRXZCLFNBQVMscUJBQXFCO0FBQzlCLFNBQVMsTUFBTSxZQUFZO0FBQzNCLFNBQVMsZUFBZ0M7QUFDekMsU0FBUyxtQkFBbUI7QUFDNUIsU0FBUyxhQUFhO0FBRXRCLE1BQU0saUJBQWdDO0FBQUEsRUFDcEMsRUFBRSxPQUFPLFdBQVcsT0FBTyxDQUFDLFlBQVksWUFBWSxTQUFTLEVBQUU7QUFBQSxFQUMvRCxFQUFFLE9BQU8sYUFBYSxPQUFPLENBQUMsUUFBUSxRQUFRLFNBQVMsRUFBRTtBQUFBLEVBQ3pELEVBQUUsT0FBTyxXQUFXLE9BQU8sQ0FBQyxTQUFTLFdBQVcsU0FBUyxFQUFFO0FBQUEsRUFDM0QsRUFBRSxPQUFPLFNBQVMsT0FBTyxDQUFDLFdBQVcsU0FBUyxTQUFTLEVBQUU7QUFDM0Q7QUFFTyxnQkFBUyxPQUFPO0FBQUEsRUFDckI7QUFBQSxFQUNBLFNBQVM7QUFBQSxFQUNULGdCQUFnQjtBQUFBLEVBQ2hCO0FBQUEsRUFDQSxlQUFlO0FBQUEsRUFDZjtBQUFBLEVBQ0EsYUFBYTtBQUFBLEVBQ2IsY0FBYztBQUNoQixHQUFnQjtBQUNkLFFBQU0sTUFBTSxPQUFvQixJQUFJO0FBQ3BDLGdCQUFjLFVBQVUsR0FBRztBQUUzQixRQUFNLGNBQWMsU0FBUyxVQUFVLEtBQUs7QUFDNUMsUUFBTSxZQUFZLGNBQWM7QUFFaEMsU0FDRSxxQkFBQyxZQUFPLFdBQXNCLEtBQVUsT0FDdEM7QUFBQSx5QkFBQyxRQUNDO0FBQUEsMEJBQUMsUUFDQywrQkFBQyxTQUFNLFdBQVUsY0FBYTtBQUFBO0FBQUEsU0FBTyxvQkFBSSxLQUFLLEdBQUUsWUFBWTtBQUFBLFNBQUUsR0FDaEU7QUFBQSxNQUVDLE9BQU8sSUFBSSxDQUFDLEVBQUUsT0FBTyxNQUFNLE1BQzFCLHFCQUFDLFFBQ0M7QUFBQSw0QkFBQyxTQUFNLFdBQVUsY0FBYyxpQkFBTTtBQUFBLFFBRXJDLG9CQUFDLFNBQUksV0FBVSw0QkFDWixnQkFBTSxJQUFJLFVBQVE7QUFDakIsZ0JBQU0sT0FBTyxPQUFPLFNBQVMsV0FDekIsSUFBSSxLQUFLLFlBQVksQ0FBQyxLQUN0QixLQUFLO0FBRVQsZ0JBQU1BLFNBQVEsT0FBTyxTQUFTLFdBQVcsT0FBTyxLQUFLO0FBRXJELGlCQUNFO0FBQUEsWUFBQztBQUFBO0FBQUEsY0FDQyxJQUFJO0FBQUEsY0FDSixXQUFVO0FBQUEsY0FDVjtBQUFBLGNBR0MsVUFBQUE7QUFBQTtBQUFBLFlBRklBO0FBQUEsVUFHUDtBQUFBLFFBRUosQ0FBQyxHQUNIO0FBQUEsV0F0QlMsS0F1QlgsQ0FDRDtBQUFBLE9BQ0g7QUFBQSxJQUVDLGFBQ0MscUJBQUMsUUFDRTtBQUFBLG9CQUNDLHFCQUFDLFFBQUssV0FBVSxvQ0FDZDtBQUFBLDRCQUFDLFNBQU0sV0FBVSxjQUFjLHdCQUFhO0FBQUEsUUFFNUMsb0JBQUMsV0FBUSxPQUFPLFNBQVU7QUFBQSxTQUM1QjtBQUFBLE1BR0QsZUFDQyxxQkFBQyxRQUFLLFdBQVUsb0NBQ2Q7QUFBQSw0QkFBQyxTQUFNLFdBQVUsY0FBYyxzQkFBVztBQUFBLFFBRTFDLG9CQUFDLGVBQVk7QUFBQSxTQUNmO0FBQUEsT0FFSjtBQUFBLEtBRUo7QUFFSjsiLAogICJuYW1lcyI6IFsibGFiZWwiXQp9Cg==
