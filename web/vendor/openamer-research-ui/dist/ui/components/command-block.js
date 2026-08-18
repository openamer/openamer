"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import { useCallback, useState } from "react";
import { cn } from "../../utils/index.js";
import { Small } from "./typography/small.js";
export function CopyButton({
  children,
  className,
  copiedLabel = "Copied!",
  label = "Copy",
  resetDelayMs = 2e3,
  text
}) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), resetDelayMs);
    });
  }, [resetDelayMs, text]);
  return /* @__PURE__ */ jsx(
    "button",
    {
      className: cn(
        "font-courier text-display cursor-pointer border-none bg-transparent text-xs",
        "tracking-widest",
        "hover:text-midground tap-highlight-transparent transition-colors",
        "flex items-center justify-center",
        copied ? "text-midground" : "text-text-secondary",
        className
      ),
      onClick: handleCopy,
      type: "button",
      children: children ?? (copied ? copiedLabel : label)
    }
  );
}
export function CommandBlock({ className, code, label }) {
  return /* @__PURE__ */ jsxs("div", { className: cn("flex flex-col gap-1", className), children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between", children: [
      /* @__PURE__ */ jsx(Small, { className: "opacity-50", children: label }),
      /* @__PURE__ */ jsx(CopyButton, { text: code })
    ] }),
    /* @__PURE__ */ jsx(
      "div",
      {
        className: cn(
          "bg-background/40 font-courier border border-current/20",
          "px-3 py-2 text-[0.6875rem] leading-relaxed lowercase"
        ),
        children: /* @__PURE__ */ jsx("code", { className: "break-all", children: code })
      }
    )
  ] });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZUNhbGxiYWNrLCB1c2VTdGF0ZSB9IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyBjbiB9IGZyb20gJy4uLy4uL3V0aWxzJ1xuXG5pbXBvcnQgeyBTbWFsbCB9IGZyb20gJy4vdHlwb2dyYXBoeS9zbWFsbCdcblxuLyoqXG4gKiBBIFwiY29weSB0byBjbGlwYm9hcmRcIiBidXR0b24gdGhhdCBicmllZmx5IHNob3dzIGEgXCJDb3BpZWQhXCIgY29uZmlybWF0aW9uLlxuICogRGVzaWduZWQgdG8gc2l0IGFsb25nc2lkZSBhIHNob3J0IGNvbW1hbmQgc3RyaW5nLCBub3QgYXMgYSBnZW5lcmFsIGJ1dHRvbi5cbiAqL1xuZXhwb3J0IGZ1bmN0aW9uIENvcHlCdXR0b24oe1xuICBjaGlsZHJlbixcbiAgY2xhc3NOYW1lLFxuICBjb3BpZWRMYWJlbCA9ICdDb3BpZWQhJyxcbiAgbGFiZWwgPSAnQ29weScsXG4gIHJlc2V0RGVsYXlNcyA9IDIwMDAsXG4gIHRleHRcbn06IENvcHlCdXR0b25Qcm9wcykge1xuICBjb25zdCBbY29waWVkLCBzZXRDb3BpZWRdID0gdXNlU3RhdGUoZmFsc2UpXG5cbiAgY29uc3QgaGFuZGxlQ29weSA9IHVzZUNhbGxiYWNrKCgpID0+IHtcbiAgICB2b2lkIG5hdmlnYXRvci5jbGlwYm9hcmQud3JpdGVUZXh0KHRleHQpLnRoZW4oKCkgPT4ge1xuICAgICAgc2V0Q29waWVkKHRydWUpXG4gICAgICBzZXRUaW1lb3V0KCgpID0+IHNldENvcGllZChmYWxzZSksIHJlc2V0RGVsYXlNcylcbiAgICB9KVxuICB9LCBbcmVzZXREZWxheU1zLCB0ZXh0XSlcblxuICByZXR1cm4gKFxuICAgIDxidXR0b25cbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICdmb250LWNvdXJpZXIgdGV4dC1kaXNwbGF5IGN1cnNvci1wb2ludGVyIGJvcmRlci1ub25lIGJnLXRyYW5zcGFyZW50IHRleHQteHMnLFxuICAgICAgICAndHJhY2tpbmctd2lkZXN0JyxcbiAgICAgICAgJ2hvdmVyOnRleHQtbWlkZ3JvdW5kIHRhcC1oaWdobGlnaHQtdHJhbnNwYXJlbnQgdHJhbnNpdGlvbi1jb2xvcnMnLFxuICAgICAgICAnZmxleCBpdGVtcy1jZW50ZXIganVzdGlmeS1jZW50ZXInLFxuICAgICAgICBjb3BpZWQgPyAndGV4dC1taWRncm91bmQnIDogJ3RleHQtdGV4dC1zZWNvbmRhcnknLFxuICAgICAgICBjbGFzc05hbWVcbiAgICAgICl9XG4gICAgICBvbkNsaWNrPXtoYW5kbGVDb3B5fVxuICAgICAgdHlwZT1cImJ1dHRvblwiXG4gICAgPlxuICAgICAge2NoaWxkcmVuID8/IChjb3BpZWQgPyBjb3BpZWRMYWJlbCA6IGxhYmVsKX1cbiAgICA8L2J1dHRvbj5cbiAgKVxufVxuXG4vKipcbiAqIEEgbGFiZWxlZCwgY29weS1hYmxlIGNvbW1hbmQgKG9yIGNvZGUpIGRpc3BsYXkuIFBhaXJzIGA8Q29weUJ1dHRvbj5gIHdpdGhcbiAqIGEgbW9ub3NwYWNlIGNvZGUgYmxvY2suIFVzZWQgZm9yIGluc3RhbGwvc2V0dXAgaW5zdHJ1Y3Rpb25zLlxuICovXG5leHBvcnQgZnVuY3Rpb24gQ29tbWFuZEJsb2NrKHsgY2xhc3NOYW1lLCBjb2RlLCBsYWJlbCB9OiBDb21tYW5kQmxvY2tQcm9wcykge1xuICByZXR1cm4gKFxuICAgIDxkaXYgY2xhc3NOYW1lPXtjbignZmxleCBmbGV4LWNvbCBnYXAtMScsIGNsYXNzTmFtZSl9PlxuICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGl0ZW1zLWNlbnRlciBqdXN0aWZ5LWJldHdlZW5cIj5cbiAgICAgICAgPFNtYWxsIGNsYXNzTmFtZT1cIm9wYWNpdHktNTBcIj57bGFiZWx9PC9TbWFsbD5cblxuICAgICAgICA8Q29weUJ1dHRvbiB0ZXh0PXtjb2RlfSAvPlxuICAgICAgPC9kaXY+XG5cbiAgICAgIDxkaXZcbiAgICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgICAnYmctYmFja2dyb3VuZC80MCBmb250LWNvdXJpZXIgYm9yZGVyIGJvcmRlci1jdXJyZW50LzIwJyxcbiAgICAgICAgICAncHgtMyBweS0yIHRleHQtWzAuNjg3NXJlbV0gbGVhZGluZy1yZWxheGVkIGxvd2VyY2FzZSdcbiAgICAgICAgKX1cbiAgICAgID5cbiAgICAgICAgPGNvZGUgY2xhc3NOYW1lPVwiYnJlYWstYWxsXCI+e2NvZGV9PC9jb2RlPlxuICAgICAgPC9kaXY+XG4gICAgPC9kaXY+XG4gIClcbn1cblxuaW50ZXJmYWNlIENvbW1hbmRCbG9ja1Byb3BzIHtcbiAgY2xhc3NOYW1lPzogc3RyaW5nXG4gIGNvZGU6IHN0cmluZ1xuICBsYWJlbDogc3RyaW5nXG59XG5cbmludGVyZmFjZSBDb3B5QnV0dG9uUHJvcHMge1xuICBjaGlsZHJlbj86IFJlYWN0LlJlYWN0Tm9kZVxuICBjbGFzc05hbWU/OiBzdHJpbmdcbiAgY29waWVkTGFiZWw/OiBzdHJpbmdcbiAgbGFiZWw/OiBzdHJpbmdcbiAgcmVzZXREZWxheU1zPzogbnVtYmVyXG4gIHRleHQ6IHN0cmluZ1xufVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQThCSSxjQXdCRSxZQXhCRjtBQTVCSixTQUFTLGFBQWEsZ0JBQWdCO0FBRXRDLFNBQVMsVUFBVTtBQUVuQixTQUFTLGFBQWE7QUFNZixnQkFBUyxXQUFXO0FBQUEsRUFDekI7QUFBQSxFQUNBO0FBQUEsRUFDQSxjQUFjO0FBQUEsRUFDZCxRQUFRO0FBQUEsRUFDUixlQUFlO0FBQUEsRUFDZjtBQUNGLEdBQW9CO0FBQ2xCLFFBQU0sQ0FBQyxRQUFRLFNBQVMsSUFBSSxTQUFTLEtBQUs7QUFFMUMsUUFBTSxhQUFhLFlBQVksTUFBTTtBQUNuQyxTQUFLLFVBQVUsVUFBVSxVQUFVLElBQUksRUFBRSxLQUFLLE1BQU07QUFDbEQsZ0JBQVUsSUFBSTtBQUNkLGlCQUFXLE1BQU0sVUFBVSxLQUFLLEdBQUcsWUFBWTtBQUFBLElBQ2pELENBQUM7QUFBQSxFQUNILEdBQUcsQ0FBQyxjQUFjLElBQUksQ0FBQztBQUV2QixTQUNFO0FBQUEsSUFBQztBQUFBO0FBQUEsTUFDQyxXQUFXO0FBQUEsUUFDVDtBQUFBLFFBQ0E7QUFBQSxRQUNBO0FBQUEsUUFDQTtBQUFBLFFBQ0EsU0FBUyxtQkFBbUI7QUFBQSxRQUM1QjtBQUFBLE1BQ0Y7QUFBQSxNQUNBLFNBQVM7QUFBQSxNQUNULE1BQUs7QUFBQSxNQUVKLHVCQUFhLFNBQVMsY0FBYztBQUFBO0FBQUEsRUFDdkM7QUFFSjtBQU1PLGdCQUFTLGFBQWEsRUFBRSxXQUFXLE1BQU0sTUFBTSxHQUFzQjtBQUMxRSxTQUNFLHFCQUFDLFNBQUksV0FBVyxHQUFHLHVCQUF1QixTQUFTLEdBQ2pEO0FBQUEseUJBQUMsU0FBSSxXQUFVLHFDQUNiO0FBQUEsMEJBQUMsU0FBTSxXQUFVLGNBQWMsaUJBQU07QUFBQSxNQUVyQyxvQkFBQyxjQUFXLE1BQU0sTUFBTTtBQUFBLE9BQzFCO0FBQUEsSUFFQTtBQUFBLE1BQUM7QUFBQTtBQUFBLFFBQ0MsV0FBVztBQUFBLFVBQ1Q7QUFBQSxVQUNBO0FBQUEsUUFDRjtBQUFBLFFBRUEsOEJBQUMsVUFBSyxXQUFVLGFBQWEsZ0JBQUs7QUFBQTtBQUFBLElBQ3BDO0FBQUEsS0FDRjtBQUVKOyIsCiAgIm5hbWVzIjogW10KfQo=
