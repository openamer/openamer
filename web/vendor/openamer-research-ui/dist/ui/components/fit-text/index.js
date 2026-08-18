"use client";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { createElement } from "react";
import { cn, polyRef } from "../../../utils/index.js";
export const FitText = polyRef(
  ({ as, children, className, max, min = "1em", style: baseStyle, ...rest }, ref) => {
    if (typeof children !== "string") {
      return null;
    }
    const style = {
      "--fit-max": max ?? "infinity * 1px",
      "--fit-min": min,
      ...baseStyle
    };
    return createElement(
      as ?? "span",
      { ...rest, className: cn("fit-text", className), ref, style },
      /* @__PURE__ */ jsxs(Fragment, { children: [
        /* @__PURE__ */ jsx("span", { children: /* @__PURE__ */ jsx("span", { children }) }),
        /* @__PURE__ */ jsx("span", { "aria-hidden": "true", children })
      ] })
    );
  }
);
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IGNyZWF0ZUVsZW1lbnQgfSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IHsgY24sIHR5cGUgUG9seVByb3BzLCBwb2x5UmVmIH0gZnJvbSAnLi4vLi4vLi4vdXRpbHMnXG5cbmV4cG9ydCBjb25zdCBGaXRUZXh0ID0gcG9seVJlZjwnc3BhbicsIE93blByb3BzPihcbiAgKFxuICAgIHsgYXMsIGNoaWxkcmVuLCBjbGFzc05hbWUsIG1heCwgbWluID0gJzFlbScsIHN0eWxlOiBiYXNlU3R5bGUsIC4uLnJlc3QgfSxcbiAgICByZWZcbiAgKSA9PiB7XG4gICAgaWYgKHR5cGVvZiBjaGlsZHJlbiAhPT0gJ3N0cmluZycpIHtcbiAgICAgIHJldHVybiBudWxsXG4gICAgfVxuXG4gICAgY29uc3Qgc3R5bGUgPSB7XG4gICAgICAnLS1maXQtbWF4JzogbWF4ID8/ICdpbmZpbml0eSAqIDFweCcsXG4gICAgICAnLS1maXQtbWluJzogbWluLFxuICAgICAgLi4uYmFzZVN0eWxlXG4gICAgfSBhcyBSZWFjdC5DU1NQcm9wZXJ0aWVzXG5cbiAgICByZXR1cm4gY3JlYXRlRWxlbWVudChcbiAgICAgIChhcyA/PyAnc3BhbicpIGFzIFJlYWN0LkVsZW1lbnRUeXBlLFxuICAgICAgeyAuLi5yZXN0LCBjbGFzc05hbWU6IGNuKCdmaXQtdGV4dCcsIGNsYXNzTmFtZSksIHJlZiwgc3R5bGUgfSxcbiAgICAgIDw+XG4gICAgICAgIDxzcGFuPlxuICAgICAgICAgIDxzcGFuPntjaGlsZHJlbn08L3NwYW4+XG4gICAgICAgIDwvc3Bhbj5cblxuICAgICAgICA8c3BhbiBhcmlhLWhpZGRlbj1cInRydWVcIj57Y2hpbGRyZW59PC9zcGFuPlxuICAgICAgPC8+XG4gICAgKVxuICB9XG4pXG5cbmludGVyZmFjZSBPd25Qcm9wcyB7XG4gIGNoaWxkcmVuOiBzdHJpbmdcbiAgbWF4Pzogc3RyaW5nXG4gIG1pbj86IHN0cmluZ1xufVxuXG5leHBvcnQgdHlwZSBGaXRUZXh0UHJvcHM8VCBleHRlbmRzIFJlYWN0LkVsZW1lbnRUeXBlID0gJ3NwYW4nPiA9IFBvbHlQcm9wczxcbiAgVCxcbiAgT3duUHJvcHNcbj5cbiJdLAogICJtYXBwaW5ncyI6ICI7QUF3Qk0sbUJBRUksS0FGSjtBQXRCTixTQUFTLHFCQUFxQjtBQUU5QixTQUFTLElBQW9CLGVBQWU7QUFFckMsYUFBTSxVQUFVO0FBQUEsRUFDckIsQ0FDRSxFQUFFLElBQUksVUFBVSxXQUFXLEtBQUssTUFBTSxPQUFPLE9BQU8sV0FBVyxHQUFHLEtBQUssR0FDdkUsUUFDRztBQUNILFFBQUksT0FBTyxhQUFhLFVBQVU7QUFDaEMsYUFBTztBQUFBLElBQ1Q7QUFFQSxVQUFNLFFBQVE7QUFBQSxNQUNaLGFBQWEsT0FBTztBQUFBLE1BQ3BCLGFBQWE7QUFBQSxNQUNiLEdBQUc7QUFBQSxJQUNMO0FBRUEsV0FBTztBQUFBLE1BQ0osTUFBTTtBQUFBLE1BQ1AsRUFBRSxHQUFHLE1BQU0sV0FBVyxHQUFHLFlBQVksU0FBUyxHQUFHLEtBQUssTUFBTTtBQUFBLE1BQzVELGlDQUNFO0FBQUEsNEJBQUMsVUFDQyw4QkFBQyxVQUFNLFVBQVMsR0FDbEI7QUFBQSxRQUVBLG9CQUFDLFVBQUssZUFBWSxRQUFRLFVBQVM7QUFBQSxTQUNyQztBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQ0Y7IiwKICAibmFtZXMiOiBbXQp9Cg==
