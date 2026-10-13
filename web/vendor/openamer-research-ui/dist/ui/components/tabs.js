"use client";
import { jsx } from "react/jsx-runtime";
import {
  useState
} from "react";
import { cn } from "../../utils/index.js";
export function Tabs({ children, className, defaultValue }) {
  const [active, setActive] = useState(defaultValue);
  return /* @__PURE__ */ jsx("div", { className: cn("flex flex-col gap-4", className), children: children(active, setActive) });
}
export function TabsList({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "inline-flex h-9 items-center justify-start border-b border-midground/15 text-text-secondary",
        className
      ),
      ...props
    }
  );
}
export function TabsTrigger({
  active,
  className,
  value: _value,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    "button",
    {
      className: cn(
        "relative inline-flex items-center justify-center whitespace-nowrap px-3 py-1.5",
        "font-mondwest text-display text-xs tracking-[0.1em] transition-all cursor-pointer",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/30",
        active ? "text-midground after:absolute after:bottom-0 after:left-0 after:right-0 after:h-px after:bg-midground" : "text-text-secondary hover:text-midground",
        className
      ),
      type: "button",
      ...props
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7XG4gIHR5cGUgQnV0dG9uSFRNTEF0dHJpYnV0ZXMsXG4gIHR5cGUgSFRNTEF0dHJpYnV0ZXMsXG4gIHR5cGUgUmVhY3ROb2RlLFxuICB1c2VTdGF0ZVxufSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuZXhwb3J0IGZ1bmN0aW9uIFRhYnMoeyBjaGlsZHJlbiwgY2xhc3NOYW1lLCBkZWZhdWx0VmFsdWUgfTogVGFic1Byb3BzKSB7XG4gIGNvbnN0IFthY3RpdmUsIHNldEFjdGl2ZV0gPSB1c2VTdGF0ZShkZWZhdWx0VmFsdWUpXG5cbiAgcmV0dXJuIChcbiAgICA8ZGl2IGNsYXNzTmFtZT17Y24oJ2ZsZXggZmxleC1jb2wgZ2FwLTQnLCBjbGFzc05hbWUpfT5cbiAgICAgIHtjaGlsZHJlbihhY3RpdmUsIHNldEFjdGl2ZSl9XG4gICAgPC9kaXY+XG4gIClcbn1cblxuZXhwb3J0IGZ1bmN0aW9uIFRhYnNMaXN0KHsgY2xhc3NOYW1lLCAuLi5wcm9wcyB9OiBIVE1MQXR0cmlidXRlczxIVE1MRGl2RWxlbWVudD4pIHtcbiAgcmV0dXJuIChcbiAgICA8ZGl2XG4gICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAnaW5saW5lLWZsZXggaC05IGl0ZW1zLWNlbnRlciBqdXN0aWZ5LXN0YXJ0IGJvcmRlci1iIGJvcmRlci1taWRncm91bmQvMTUgdGV4dC10ZXh0LXNlY29uZGFyeScsXG4gICAgICAgIGNsYXNzTmFtZVxuICAgICAgKX1cbiAgICAgIHsuLi5wcm9wc31cbiAgICAvPlxuICApXG59XG5cbmV4cG9ydCBmdW5jdGlvbiBUYWJzVHJpZ2dlcih7XG4gIGFjdGl2ZSxcbiAgY2xhc3NOYW1lLFxuICB2YWx1ZTogX3ZhbHVlLFxuICAuLi5wcm9wc1xufTogVGFic1RyaWdnZXJQcm9wcykge1xuICByZXR1cm4gKFxuICAgIDxidXR0b25cbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICdyZWxhdGl2ZSBpbmxpbmUtZmxleCBpdGVtcy1jZW50ZXIganVzdGlmeS1jZW50ZXIgd2hpdGVzcGFjZS1ub3dyYXAgcHgtMyBweS0xLjUnLFxuICAgICAgICAnZm9udC1tb25kd2VzdCB0ZXh0LWRpc3BsYXkgdGV4dC14cyB0cmFja2luZy1bMC4xZW1dIHRyYW5zaXRpb24tYWxsIGN1cnNvci1wb2ludGVyJyxcbiAgICAgICAgJ2ZvY3VzLXZpc2libGU6b3V0bGluZS1ub25lIGZvY3VzLXZpc2libGU6cmluZy0xIGZvY3VzLXZpc2libGU6cmluZy1taWRncm91bmQvMzAnLFxuICAgICAgICBhY3RpdmVcbiAgICAgICAgICA/ICd0ZXh0LW1pZGdyb3VuZCBhZnRlcjphYnNvbHV0ZSBhZnRlcjpib3R0b20tMCBhZnRlcjpsZWZ0LTAgYWZ0ZXI6cmlnaHQtMCBhZnRlcjpoLXB4IGFmdGVyOmJnLW1pZGdyb3VuZCdcbiAgICAgICAgICA6ICd0ZXh0LXRleHQtc2Vjb25kYXJ5IGhvdmVyOnRleHQtbWlkZ3JvdW5kJyxcbiAgICAgICAgY2xhc3NOYW1lXG4gICAgICApfVxuICAgICAgdHlwZT1cImJ1dHRvblwiXG4gICAgICB7Li4ucHJvcHN9XG4gICAgLz5cbiAgKVxufVxuXG5pbnRlcmZhY2UgVGFic1Byb3BzIHtcbiAgY2hpbGRyZW46IChhY3RpdmU6IHN0cmluZywgc2V0QWN0aXZlOiAodmFsdWU6IHN0cmluZykgPT4gdm9pZCkgPT4gUmVhY3ROb2RlXG4gIGNsYXNzTmFtZT86IHN0cmluZ1xuICBkZWZhdWx0VmFsdWU6IHN0cmluZ1xufVxuXG5pbnRlcmZhY2UgVGFic1RyaWdnZXJQcm9wcyBleHRlbmRzIEJ1dHRvbkhUTUxBdHRyaWJ1dGVzPEhUTUxCdXR0b25FbGVtZW50PiB7XG4gIGFjdGl2ZTogYm9vbGVhblxuICB2YWx1ZTogc3RyaW5nXG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBZUk7QUFiSjtBQUFBLEVBSUU7QUFBQSxPQUNLO0FBRVAsU0FBUyxVQUFVO0FBRVosZ0JBQVMsS0FBSyxFQUFFLFVBQVUsV0FBVyxhQUFhLEdBQWM7QUFDckUsUUFBTSxDQUFDLFFBQVEsU0FBUyxJQUFJLFNBQVMsWUFBWTtBQUVqRCxTQUNFLG9CQUFDLFNBQUksV0FBVyxHQUFHLHVCQUF1QixTQUFTLEdBQ2hELG1CQUFTLFFBQVEsU0FBUyxHQUM3QjtBQUVKO0FBRU8sZ0JBQVMsU0FBUyxFQUFFLFdBQVcsR0FBRyxNQUFNLEdBQW1DO0FBQ2hGLFNBQ0U7QUFBQSxJQUFDO0FBQUE7QUFBQSxNQUNDLFdBQVc7QUFBQSxRQUNUO0FBQUEsUUFDQTtBQUFBLE1BQ0Y7QUFBQSxNQUNDLEdBQUc7QUFBQTtBQUFBLEVBQ047QUFFSjtBQUVPLGdCQUFTLFlBQVk7QUFBQSxFQUMxQjtBQUFBLEVBQ0E7QUFBQSxFQUNBLE9BQU87QUFBQSxFQUNQLEdBQUc7QUFDTCxHQUFxQjtBQUNuQixTQUNFO0FBQUEsSUFBQztBQUFBO0FBQUEsTUFDQyxXQUFXO0FBQUEsUUFDVDtBQUFBLFFBQ0E7QUFBQSxRQUNBO0FBQUEsUUFDQSxTQUNJLDBHQUNBO0FBQUEsUUFDSjtBQUFBLE1BQ0Y7QUFBQSxNQUNBLE1BQUs7QUFBQSxNQUNKLEdBQUc7QUFBQTtBQUFBLEVBQ047QUFFSjsiLAogICJuYW1lcyI6IFtdCn0K
