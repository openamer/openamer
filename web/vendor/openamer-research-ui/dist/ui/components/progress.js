import { jsx, jsxs } from "react/jsx-runtime";
import { cn } from "../../utils/index.js";
import { Typography } from "./typography/index.js";
export const Progress = ({
  animate = true,
  barProps,
  children,
  className,
  speed = 0.4,
  value,
  ...props
}) => /* @__PURE__ */ jsxs(
  "div",
  {
    className: cn(
      "relative flex min-h-[2.3rem] min-w-0 flex-1 items-stretch overflow-hidden",
      className
    ),
    ...props,
    children: [
      /* @__PURE__ */ jsx(
        Typography,
        {
          ...barProps,
          className: cn(
            "shrink-0 translate-y-0.5 truncate py-2",
            "bg-midground/20",
            children ? "px-2" : "px-0",
            barProps?.className
          ),
          mono: true,
          style: {
            ...animate && { transition: `width ${speed}s steps(10, end)` },
            width: `${value}%`,
            ...barProps?.style
          },
          children
        }
      ),
      /* @__PURE__ */ jsx(
        "div",
        {
          className: "flex-1",
          style: {
            "--x": ".5rem",
            backgroundImage: `repeating-linear-gradient(to right, transparent 0 var(--x), color-mix(in srgb, var(--color-midground) 17%, transparent) var(--x) calc(var(--x) + 1px))`
          }
        }
      )
    ]
  }
);
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuaW1wb3J0IHsgVHlwb2dyYXBoeSwgdHlwZSBUeXBvZ3JhcGh5UHJvcHMgfSBmcm9tICcuL3R5cG9ncmFwaHknXG5cbmV4cG9ydCBjb25zdCBQcm9ncmVzcyA9ICh7XG4gIGFuaW1hdGUgPSB0cnVlLFxuICBiYXJQcm9wcyxcbiAgY2hpbGRyZW4sXG4gIGNsYXNzTmFtZSxcbiAgc3BlZWQgPSAwLjQsXG4gIHZhbHVlLFxuICAuLi5wcm9wc1xufTogUHJvZ3Jlc3NQcm9wcykgPT4gKFxuICA8ZGl2XG4gICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICdyZWxhdGl2ZSBmbGV4IG1pbi1oLVsyLjNyZW1dIG1pbi13LTAgZmxleC0xIGl0ZW1zLXN0cmV0Y2ggb3ZlcmZsb3ctaGlkZGVuJyxcbiAgICAgIGNsYXNzTmFtZVxuICAgICl9XG4gICAgey4uLnByb3BzfVxuICA+XG4gICAgPFR5cG9ncmFwaHlcbiAgICAgIHsuLi5iYXJQcm9wc31cbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICdzaHJpbmstMCB0cmFuc2xhdGUteS0wLjUgdHJ1bmNhdGUgcHktMicsXG4gICAgICAgICdiZy1taWRncm91bmQvMjAnLFxuICAgICAgICBjaGlsZHJlbiA/ICdweC0yJyA6ICdweC0wJyxcbiAgICAgICAgYmFyUHJvcHM/LmNsYXNzTmFtZVxuICAgICAgKX1cbiAgICAgIG1vbm9cbiAgICAgIHN0eWxlPXt7XG4gICAgICAgIC4uLihhbmltYXRlICYmIHsgdHJhbnNpdGlvbjogYHdpZHRoICR7c3BlZWR9cyBzdGVwcygxMCwgZW5kKWAgfSksXG4gICAgICAgIHdpZHRoOiBgJHt2YWx1ZX0lYCxcbiAgICAgICAgLi4uYmFyUHJvcHM/LnN0eWxlXG4gICAgICB9fVxuICAgID5cbiAgICAgIHtjaGlsZHJlbn1cbiAgICA8L1R5cG9ncmFwaHk+XG5cbiAgICA8ZGl2XG4gICAgICBjbGFzc05hbWU9XCJmbGV4LTFcIlxuICAgICAgc3R5bGU9e1xuICAgICAgICB7XG4gICAgICAgICAgJy0teCc6ICcuNXJlbScsXG4gICAgICAgICAgYmFja2dyb3VuZEltYWdlOiBgcmVwZWF0aW5nLWxpbmVhci1ncmFkaWVudCh0byByaWdodCwgdHJhbnNwYXJlbnQgMCB2YXIoLS14KSwgY29sb3ItbWl4KGluIHNyZ2IsIHZhcigtLWNvbG9yLW1pZGdyb3VuZCkgMTclLCB0cmFuc3BhcmVudCkgdmFyKC0teCkgY2FsYyh2YXIoLS14KSArIDFweCkpYFxuICAgICAgICB9IGFzIFJlYWN0LkNTU1Byb3BlcnRpZXNcbiAgICAgIH1cbiAgICAvPlxuICA8L2Rpdj5cbilcblxuaW50ZXJmYWNlIFByb2dyZXNzUHJvcHMgZXh0ZW5kcyBSZWFjdC5Db21wb25lbnRQcm9wczwnZGl2Jz4ge1xuICBhbmltYXRlPzogYm9vbGVhblxuICBiYXJQcm9wcz86IFR5cG9ncmFwaHlQcm9wczwnc3Bhbic+XG4gIHNwZWVkPzogbnVtYmVyXG4gIHZhbHVlOiBudW1iZXJcbn1cbiJdLAogICJtYXBwaW5ncyI6ICJBQWFFLFNBT0UsS0FQRjtBQWJGLFNBQVMsVUFBVTtBQUVuQixTQUFTLGtCQUF3QztBQUUxQyxhQUFNLFdBQVcsQ0FBQztBQUFBLEVBQ3ZCLFVBQVU7QUFBQSxFQUNWO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFBQSxFQUNBLFFBQVE7QUFBQSxFQUNSO0FBQUEsRUFDQSxHQUFHO0FBQ0wsTUFDRTtBQUFBLEVBQUM7QUFBQTtBQUFBLElBQ0MsV0FBVztBQUFBLE1BQ1Q7QUFBQSxNQUNBO0FBQUEsSUFDRjtBQUFBLElBQ0MsR0FBRztBQUFBLElBRUo7QUFBQTtBQUFBLFFBQUM7QUFBQTtBQUFBLFVBQ0UsR0FBRztBQUFBLFVBQ0osV0FBVztBQUFBLFlBQ1Q7QUFBQSxZQUNBO0FBQUEsWUFDQSxXQUFXLFNBQVM7QUFBQSxZQUNwQixVQUFVO0FBQUEsVUFDWjtBQUFBLFVBQ0EsTUFBSTtBQUFBLFVBQ0osT0FBTztBQUFBLFlBQ0wsR0FBSSxXQUFXLEVBQUUsWUFBWSxTQUFTLEtBQUssbUJBQW1CO0FBQUEsWUFDOUQsT0FBTyxHQUFHLEtBQUs7QUFBQSxZQUNmLEdBQUcsVUFBVTtBQUFBLFVBQ2Y7QUFBQSxVQUVDO0FBQUE7QUFBQSxNQUNIO0FBQUEsTUFFQTtBQUFBLFFBQUM7QUFBQTtBQUFBLFVBQ0MsV0FBVTtBQUFBLFVBQ1YsT0FDRTtBQUFBLFlBQ0UsT0FBTztBQUFBLFlBQ1AsaUJBQWlCO0FBQUEsVUFDbkI7QUFBQTtBQUFBLE1BRUo7QUFBQTtBQUFBO0FBQ0Y7IiwKICAibmFtZXMiOiBbXQp9Cg==
