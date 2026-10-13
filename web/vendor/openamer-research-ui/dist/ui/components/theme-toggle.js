"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import { useStore } from "@nanostores/react";
import { cn } from "../../utils/index.js";
import { $lightMode, toggleLens } from "./overlays/index.js";
export function ThemeToggle({ className, style }) {
  const light = useStore($lightMode);
  return /* @__PURE__ */ jsxs(
    "button",
    {
      "aria-label": light ? "Switch to dark mode" : "Switch to light mode",
      className: cn(
        "relative flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full",
        "border border-current/25 bg-current/8 transition-colors",
        "hover:bg-current/15",
        className
      ),
      onClick: toggleLens,
      style,
      type: "button",
      children: [
        /* @__PURE__ */ jsxs(
          "svg",
          {
            className: "absolute left-1 size-3.5 opacity-40",
            fill: "none",
            stroke: "currentColor",
            strokeLinecap: "round",
            strokeLinejoin: "round",
            strokeWidth: 2,
            viewBox: "0 0 24 24",
            children: [
              /* @__PURE__ */ jsx("circle", { cx: 12, cy: 12, r: 5 }),
              /* @__PURE__ */ jsx("path", { d: "M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" })
            ]
          }
        ),
        /* @__PURE__ */ jsx(
          "svg",
          {
            className: "absolute right-1 size-3.5 opacity-40",
            fill: "none",
            stroke: "currentColor",
            strokeLinecap: "round",
            strokeLinejoin: "round",
            strokeWidth: 2,
            viewBox: "0 0 24 24",
            children: /* @__PURE__ */ jsx("path", { d: "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" })
          }
        ),
        /* @__PURE__ */ jsx(
          "span",
          {
            "aria-hidden": true,
            className: cn(
              "bg-midground absolute size-4 rounded-full",
              "transition-transform duration-200 ease-out"
            ),
            style: { transform: `translateX(${light ? 2 : 22}px)` }
          }
        )
      ]
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZVN0b3JlIH0gZnJvbSAnQG5hbm9zdG9yZXMvcmVhY3QnXG5cbmltcG9ydCB7IGNuIH0gZnJvbSAnLi4vLi4vdXRpbHMnXG5cbmltcG9ydCB7ICRsaWdodE1vZGUsIHRvZ2dsZUxlbnMgfSBmcm9tICcuL292ZXJsYXlzJ1xuXG5leHBvcnQgZnVuY3Rpb24gVGhlbWVUb2dnbGUoeyBjbGFzc05hbWUsIHN0eWxlIH06IFRoZW1lVG9nZ2xlUHJvcHMpIHtcbiAgY29uc3QgbGlnaHQgPSB1c2VTdG9yZSgkbGlnaHRNb2RlKVxuXG4gIHJldHVybiAoXG4gICAgPGJ1dHRvblxuICAgICAgYXJpYS1sYWJlbD17bGlnaHQgPyAnU3dpdGNoIHRvIGRhcmsgbW9kZScgOiAnU3dpdGNoIHRvIGxpZ2h0IG1vZGUnfVxuICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgJ3JlbGF0aXZlIGZsZXggaC02IHctMTEgc2hyaW5rLTAgY3Vyc29yLXBvaW50ZXIgaXRlbXMtY2VudGVyIHJvdW5kZWQtZnVsbCcsXG4gICAgICAgICdib3JkZXIgYm9yZGVyLWN1cnJlbnQvMjUgYmctY3VycmVudC84IHRyYW5zaXRpb24tY29sb3JzJyxcbiAgICAgICAgJ2hvdmVyOmJnLWN1cnJlbnQvMTUnLFxuICAgICAgICBjbGFzc05hbWVcbiAgICAgICl9XG4gICAgICBvbkNsaWNrPXt0b2dnbGVMZW5zfVxuICAgICAgc3R5bGU9e3N0eWxlfVxuICAgICAgdHlwZT1cImJ1dHRvblwiXG4gICAgPlxuICAgICAgPHN2Z1xuICAgICAgICBjbGFzc05hbWU9XCJhYnNvbHV0ZSBsZWZ0LTEgc2l6ZS0zLjUgb3BhY2l0eS00MFwiXG4gICAgICAgIGZpbGw9XCJub25lXCJcbiAgICAgICAgc3Ryb2tlPVwiY3VycmVudENvbG9yXCJcbiAgICAgICAgc3Ryb2tlTGluZWNhcD1cInJvdW5kXCJcbiAgICAgICAgc3Ryb2tlTGluZWpvaW49XCJyb3VuZFwiXG4gICAgICAgIHN0cm9rZVdpZHRoPXsyfVxuICAgICAgICB2aWV3Qm94PVwiMCAwIDI0IDI0XCJcbiAgICAgID5cbiAgICAgICAgPGNpcmNsZSBjeD17MTJ9IGN5PXsxMn0gcj17NX0gLz5cblxuICAgICAgICA8cGF0aCBkPVwiTTEyIDF2Mk0xMiAyMXYyTTQuMjIgNC4yMmwxLjQyIDEuNDJNMTguMzYgMTguMzZsMS40MiAxLjQyTTEgMTJoMk0yMSAxMmgyTTQuMjIgMTkuNzhsMS40Mi0xLjQyTTE4LjM2IDUuNjRsMS40Mi0xLjQyXCIgLz5cbiAgICAgIDwvc3ZnPlxuXG4gICAgICA8c3ZnXG4gICAgICAgIGNsYXNzTmFtZT1cImFic29sdXRlIHJpZ2h0LTEgc2l6ZS0zLjUgb3BhY2l0eS00MFwiXG4gICAgICAgIGZpbGw9XCJub25lXCJcbiAgICAgICAgc3Ryb2tlPVwiY3VycmVudENvbG9yXCJcbiAgICAgICAgc3Ryb2tlTGluZWNhcD1cInJvdW5kXCJcbiAgICAgICAgc3Ryb2tlTGluZWpvaW49XCJyb3VuZFwiXG4gICAgICAgIHN0cm9rZVdpZHRoPXsyfVxuICAgICAgICB2aWV3Qm94PVwiMCAwIDI0IDI0XCJcbiAgICAgID5cbiAgICAgICAgPHBhdGggZD1cIk0yMSAxMi43OUE5IDkgMCAxIDEgMTEuMjEgMyA3IDcgMCAwIDAgMjEgMTIuNzl6XCIgLz5cbiAgICAgIDwvc3ZnPlxuXG4gICAgICA8c3BhblxuICAgICAgICBhcmlhLWhpZGRlblxuICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICdiZy1taWRncm91bmQgYWJzb2x1dGUgc2l6ZS00IHJvdW5kZWQtZnVsbCcsXG4gICAgICAgICAgJ3RyYW5zaXRpb24tdHJhbnNmb3JtIGR1cmF0aW9uLTIwMCBlYXNlLW91dCdcbiAgICAgICAgKX1cbiAgICAgICAgc3R5bGU9e3sgdHJhbnNmb3JtOiBgdHJhbnNsYXRlWCgke2xpZ2h0ID8gMiA6IDIyfXB4KWAgfX1cbiAgICAgIC8+XG4gICAgPC9idXR0b24+XG4gIClcbn1cblxuaW50ZXJmYWNlIFRoZW1lVG9nZ2xlUHJvcHMge1xuICBjbGFzc05hbWU/OiBzdHJpbmdcbiAgc3R5bGU/OiBSZWFjdC5DU1NQcm9wZXJ0aWVzXG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBd0JNLFNBU0UsS0FURjtBQXRCTixTQUFTLGdCQUFnQjtBQUV6QixTQUFTLFVBQVU7QUFFbkIsU0FBUyxZQUFZLGtCQUFrQjtBQUVoQyxnQkFBUyxZQUFZLEVBQUUsV0FBVyxNQUFNLEdBQXFCO0FBQ2xFLFFBQU0sUUFBUSxTQUFTLFVBQVU7QUFFakMsU0FDRTtBQUFBLElBQUM7QUFBQTtBQUFBLE1BQ0MsY0FBWSxRQUFRLHdCQUF3QjtBQUFBLE1BQzVDLFdBQVc7QUFBQSxRQUNUO0FBQUEsUUFDQTtBQUFBLFFBQ0E7QUFBQSxRQUNBO0FBQUEsTUFDRjtBQUFBLE1BQ0EsU0FBUztBQUFBLE1BQ1Q7QUFBQSxNQUNBLE1BQUs7QUFBQSxNQUVMO0FBQUE7QUFBQSxVQUFDO0FBQUE7QUFBQSxZQUNDLFdBQVU7QUFBQSxZQUNWLE1BQUs7QUFBQSxZQUNMLFFBQU87QUFBQSxZQUNQLGVBQWM7QUFBQSxZQUNkLGdCQUFlO0FBQUEsWUFDZixhQUFhO0FBQUEsWUFDYixTQUFRO0FBQUEsWUFFUjtBQUFBLGtDQUFDLFlBQU8sSUFBSSxJQUFJLElBQUksSUFBSSxHQUFHLEdBQUc7QUFBQSxjQUU5QixvQkFBQyxVQUFLLEdBQUUsc0hBQXFIO0FBQUE7QUFBQTtBQUFBLFFBQy9IO0FBQUEsUUFFQTtBQUFBLFVBQUM7QUFBQTtBQUFBLFlBQ0MsV0FBVTtBQUFBLFlBQ1YsTUFBSztBQUFBLFlBQ0wsUUFBTztBQUFBLFlBQ1AsZUFBYztBQUFBLFlBQ2QsZ0JBQWU7QUFBQSxZQUNmLGFBQWE7QUFBQSxZQUNiLFNBQVE7QUFBQSxZQUVSLDhCQUFDLFVBQUssR0FBRSxtREFBa0Q7QUFBQTtBQUFBLFFBQzVEO0FBQUEsUUFFQTtBQUFBLFVBQUM7QUFBQTtBQUFBLFlBQ0MsZUFBVztBQUFBLFlBQ1gsV0FBVztBQUFBLGNBQ1Q7QUFBQSxjQUNBO0FBQUEsWUFDRjtBQUFBLFlBQ0EsT0FBTyxFQUFFLFdBQVcsY0FBYyxRQUFRLElBQUksRUFBRSxNQUFNO0FBQUE7QUFBQSxRQUN4RDtBQUFBO0FBQUE7QUFBQSxFQUNGO0FBRUo7IiwKICAibmFtZXMiOiBbXQp9Cg==
