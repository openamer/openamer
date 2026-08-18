"use client";
import { jsx } from "react/jsx-runtime";
import { forwardRef } from "react";
import { cn } from "../../utils/index.js";
export const ListItem = forwardRef(
  function ListItem2({ active = false, children, className, type = "button", ...props }, ref) {
    return /* @__PURE__ */ jsx(
      "button",
      {
        className: cn(
          "group relative flex w-full items-center gap-2 px-3 py-2 text-left",
          "font-courier text-sm transition-colors cursor-pointer",
          "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/30",
          "disabled:cursor-not-allowed disabled:text-text-disabled",
          active ? "bg-midground/10 text-midground" : "text-text-secondary hover:text-midground hover:bg-midground/5",
          className
        ),
        "data-active": active || void 0,
        ref,
        type,
        ...props,
        children
      }
    );
  }
);
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IGZvcndhcmRSZWYsIHR5cGUgQnV0dG9uSFRNTEF0dHJpYnV0ZXMgfSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuZXhwb3J0IGNvbnN0IExpc3RJdGVtID0gZm9yd2FyZFJlZjxIVE1MQnV0dG9uRWxlbWVudCwgTGlzdEl0ZW1Qcm9wcz4oXG4gIGZ1bmN0aW9uIExpc3RJdGVtKFxuICAgIHsgYWN0aXZlID0gZmFsc2UsIGNoaWxkcmVuLCBjbGFzc05hbWUsIHR5cGUgPSAnYnV0dG9uJywgLi4ucHJvcHMgfSxcbiAgICByZWZcbiAgKSB7XG4gICAgcmV0dXJuIChcbiAgICAgIDxidXR0b25cbiAgICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgICAnZ3JvdXAgcmVsYXRpdmUgZmxleCB3LWZ1bGwgaXRlbXMtY2VudGVyIGdhcC0yIHB4LTMgcHktMiB0ZXh0LWxlZnQnLFxuICAgICAgICAgICdmb250LWNvdXJpZXIgdGV4dC1zbSB0cmFuc2l0aW9uLWNvbG9ycyBjdXJzb3ItcG9pbnRlcicsXG4gICAgICAgICAgJ2ZvY3VzLXZpc2libGU6b3V0bGluZS1ub25lIGZvY3VzLXZpc2libGU6cmluZy0xIGZvY3VzLXZpc2libGU6cmluZy1taWRncm91bmQvMzAnLFxuICAgICAgICAgICdkaXNhYmxlZDpjdXJzb3Itbm90LWFsbG93ZWQgZGlzYWJsZWQ6dGV4dC10ZXh0LWRpc2FibGVkJyxcbiAgICAgICAgICBhY3RpdmVcbiAgICAgICAgICAgID8gJ2JnLW1pZGdyb3VuZC8xMCB0ZXh0LW1pZGdyb3VuZCdcbiAgICAgICAgICAgIDogJ3RleHQtdGV4dC1zZWNvbmRhcnkgaG92ZXI6dGV4dC1taWRncm91bmQgaG92ZXI6YmctbWlkZ3JvdW5kLzUnLFxuICAgICAgICAgIGNsYXNzTmFtZVxuICAgICAgICApfVxuICAgICAgICBkYXRhLWFjdGl2ZT17YWN0aXZlIHx8IHVuZGVmaW5lZH1cbiAgICAgICAgcmVmPXtyZWZ9XG4gICAgICAgIHR5cGU9e3R5cGV9XG4gICAgICAgIHsuLi5wcm9wc31cbiAgICAgID5cbiAgICAgICAge2NoaWxkcmVufVxuICAgICAgPC9idXR0b24+XG4gICAgKVxuICB9XG4pXG5cbmludGVyZmFjZSBMaXN0SXRlbVByb3BzIGV4dGVuZHMgQnV0dG9uSFRNTEF0dHJpYnV0ZXM8SFRNTEJ1dHRvbkVsZW1lbnQ+IHtcbiAgYWN0aXZlPzogYm9vbGVhblxufVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQVlNO0FBVk4sU0FBUyxrQkFBNkM7QUFFdEQsU0FBUyxVQUFVO0FBRVosYUFBTSxXQUFXO0FBQUEsRUFDdEIsU0FBU0EsVUFDUCxFQUFFLFNBQVMsT0FBTyxVQUFVLFdBQVcsT0FBTyxVQUFVLEdBQUcsTUFBTSxHQUNqRSxLQUNBO0FBQ0EsV0FDRTtBQUFBLE1BQUM7QUFBQTtBQUFBLFFBQ0MsV0FBVztBQUFBLFVBQ1Q7QUFBQSxVQUNBO0FBQUEsVUFDQTtBQUFBLFVBQ0E7QUFBQSxVQUNBLFNBQ0ksbUNBQ0E7QUFBQSxVQUNKO0FBQUEsUUFDRjtBQUFBLFFBQ0EsZUFBYSxVQUFVO0FBQUEsUUFDdkI7QUFBQSxRQUNBO0FBQUEsUUFDQyxHQUFHO0FBQUEsUUFFSDtBQUFBO0FBQUEsSUFDSDtBQUFBLEVBRUo7QUFDRjsiLAogICJuYW1lcyI6IFsiTGlzdEl0ZW0iXQp9Cg==
