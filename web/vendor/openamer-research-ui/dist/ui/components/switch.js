"use client";
import { jsx } from "react/jsx-runtime";
import { forwardRef } from "react";
import { cn } from "../../utils/index.js";
export const Switch = forwardRef(function Switch2({ checked, className, disabled, id, onCheckedChange, ...props }, ref) {
  return /* @__PURE__ */ jsx(
    "button",
    {
      "aria-checked": checked,
      className: cn(
        "peer inline-flex h-5 w-9 shrink-0 items-center border transition-colors cursor-pointer",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/30",
        "disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-midground/15 border-midground/30" : "bg-background border-midground/20",
        className
      ),
      disabled,
      id,
      onClick: () => onCheckedChange(!checked),
      ref,
      role: "switch",
      type: "button",
      ...props,
      children: /* @__PURE__ */ jsx(
        "span",
        {
          "aria-hidden": true,
          className: cn(
            "pointer-events-none block h-3.5 w-3.5 transition-transform",
            checked ? "translate-x-4 bg-midground" : "translate-x-0.5 bg-midground/40"
          )
        }
      )
    }
  );
});
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHR5cGUgQnV0dG9uSFRNTEF0dHJpYnV0ZXMsIGZvcndhcmRSZWYgfSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuZXhwb3J0IGNvbnN0IFN3aXRjaCA9IGZvcndhcmRSZWY8SFRNTEJ1dHRvbkVsZW1lbnQsIFN3aXRjaFByb3BzPihmdW5jdGlvbiBTd2l0Y2goXG4gIHsgY2hlY2tlZCwgY2xhc3NOYW1lLCBkaXNhYmxlZCwgaWQsIG9uQ2hlY2tlZENoYW5nZSwgLi4ucHJvcHMgfSxcbiAgcmVmXG4pIHtcbiAgcmV0dXJuIChcbiAgICA8YnV0dG9uXG4gICAgICBhcmlhLWNoZWNrZWQ9e2NoZWNrZWR9XG4gICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAncGVlciBpbmxpbmUtZmxleCBoLTUgdy05IHNocmluay0wIGl0ZW1zLWNlbnRlciBib3JkZXIgdHJhbnNpdGlvbi1jb2xvcnMgY3Vyc29yLXBvaW50ZXInLFxuICAgICAgICAnZm9jdXMtdmlzaWJsZTpvdXRsaW5lLW5vbmUgZm9jdXMtdmlzaWJsZTpyaW5nLTEgZm9jdXMtdmlzaWJsZTpyaW5nLW1pZGdyb3VuZC8zMCcsXG4gICAgICAgICdkaXNhYmxlZDpjdXJzb3Itbm90LWFsbG93ZWQgZGlzYWJsZWQ6b3BhY2l0eS01MCcsXG4gICAgICAgIGNoZWNrZWRcbiAgICAgICAgICA/ICdiZy1taWRncm91bmQvMTUgYm9yZGVyLW1pZGdyb3VuZC8zMCdcbiAgICAgICAgICA6ICdiZy1iYWNrZ3JvdW5kIGJvcmRlci1taWRncm91bmQvMjAnLFxuICAgICAgICBjbGFzc05hbWVcbiAgICAgICl9XG4gICAgICBkaXNhYmxlZD17ZGlzYWJsZWR9XG4gICAgICBpZD17aWR9XG4gICAgICBvbkNsaWNrPXsoKSA9PiBvbkNoZWNrZWRDaGFuZ2UoIWNoZWNrZWQpfVxuICAgICAgcmVmPXtyZWZ9XG4gICAgICByb2xlPVwic3dpdGNoXCJcbiAgICAgIHR5cGU9XCJidXR0b25cIlxuICAgICAgey4uLnByb3BzfVxuICAgID5cbiAgICAgIDxzcGFuXG4gICAgICAgIGFyaWEtaGlkZGVuXG4gICAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICAgJ3BvaW50ZXItZXZlbnRzLW5vbmUgYmxvY2sgaC0zLjUgdy0zLjUgdHJhbnNpdGlvbi10cmFuc2Zvcm0nLFxuICAgICAgICAgIGNoZWNrZWRcbiAgICAgICAgICAgID8gJ3RyYW5zbGF0ZS14LTQgYmctbWlkZ3JvdW5kJ1xuICAgICAgICAgICAgOiAndHJhbnNsYXRlLXgtMC41IGJnLW1pZGdyb3VuZC80MCdcbiAgICAgICAgKX1cbiAgICAgIC8+XG4gICAgPC9idXR0b24+XG4gIClcbn0pXG5cbmludGVyZmFjZSBTd2l0Y2hQcm9wc1xuICBleHRlbmRzIE9taXQ8QnV0dG9uSFRNTEF0dHJpYnV0ZXM8SFRNTEJ1dHRvbkVsZW1lbnQ+LCAnb25DaGFuZ2UnPiB7XG4gIGNoZWNrZWQ6IGJvb2xlYW5cbiAgb25DaGVja2VkQ2hhbmdlOiAoY2hlY2tlZDogYm9vbGVhbikgPT4gdm9pZFxufVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQThCTTtBQTVCTixTQUFvQyxrQkFBa0I7QUFFdEQsU0FBUyxVQUFVO0FBRVosYUFBTSxTQUFTLFdBQTJDLFNBQVNBLFFBQ3hFLEVBQUUsU0FBUyxXQUFXLFVBQVUsSUFBSSxpQkFBaUIsR0FBRyxNQUFNLEdBQzlELEtBQ0E7QUFDQSxTQUNFO0FBQUEsSUFBQztBQUFBO0FBQUEsTUFDQyxnQkFBYztBQUFBLE1BQ2QsV0FBVztBQUFBLFFBQ1Q7QUFBQSxRQUNBO0FBQUEsUUFDQTtBQUFBLFFBQ0EsVUFDSSx3Q0FDQTtBQUFBLFFBQ0o7QUFBQSxNQUNGO0FBQUEsTUFDQTtBQUFBLE1BQ0E7QUFBQSxNQUNBLFNBQVMsTUFBTSxnQkFBZ0IsQ0FBQyxPQUFPO0FBQUEsTUFDdkM7QUFBQSxNQUNBLE1BQUs7QUFBQSxNQUNMLE1BQUs7QUFBQSxNQUNKLEdBQUc7QUFBQSxNQUVKO0FBQUEsUUFBQztBQUFBO0FBQUEsVUFDQyxlQUFXO0FBQUEsVUFDWCxXQUFXO0FBQUEsWUFDVDtBQUFBLFlBQ0EsVUFDSSwrQkFDQTtBQUFBLFVBQ047QUFBQTtBQUFBLE1BQ0Y7QUFBQTtBQUFBLEVBQ0Y7QUFFSixDQUFDOyIsCiAgIm5hbWVzIjogWyJTd2l0Y2giXQp9Cg==
