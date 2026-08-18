"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import { cn } from "../../utils/index.js";
export function Segmented({
  className,
  onChange,
  options,
  size = "sm",
  value
}) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "inline-flex border border-midground/15 bg-background/30",
        className
      ),
      role: "radiogroup",
      children: options.map((opt) => {
        const active = opt.value === value;
        return /* @__PURE__ */ jsx(
          "button",
          {
            "aria-checked": active,
            className: cn(
              "font-mondwest text-display tracking-[0.1em]",
              "transition-colors cursor-pointer whitespace-nowrap",
              "border-r border-midground/15 last:border-r-0",
              "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/30",
              size === "sm" && "h-7 px-2.5 text-xs",
              size === "md" && "h-8 px-3 text-xs",
              active ? "bg-midground text-background" : "text-text-secondary hover:bg-midground/10 hover:text-midground"
            ),
            onClick: () => onChange(opt.value),
            role: "radio",
            type: "button",
            children: opt.label
          },
          opt.value
        );
      })
    }
  );
}
export function FilterGroup({ children, className, label }) {
  return /* @__PURE__ */ jsxs("div", { className: cn("flex items-center gap-2", className), children: [
    /* @__PURE__ */ jsx("span", { className: "font-mondwest text-display text-xs tracking-[0.12em] text-text-tertiary", children: label }),
    children
  ] });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHR5cGUgUmVhY3ROb2RlIH0gZnJvbSAncmVhY3QnXG5cbmltcG9ydCB7IGNuIH0gZnJvbSAnLi4vLi4vdXRpbHMnXG5cbmV4cG9ydCBmdW5jdGlvbiBTZWdtZW50ZWQ8VCBleHRlbmRzIHN0cmluZz4oe1xuICBjbGFzc05hbWUsXG4gIG9uQ2hhbmdlLFxuICBvcHRpb25zLFxuICBzaXplID0gJ3NtJyxcbiAgdmFsdWVcbn06IFNlZ21lbnRlZFByb3BzPFQ+KSB7XG4gIHJldHVybiAoXG4gICAgPGRpdlxuICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgJ2lubGluZS1mbGV4IGJvcmRlciBib3JkZXItbWlkZ3JvdW5kLzE1IGJnLWJhY2tncm91bmQvMzAnLFxuICAgICAgICBjbGFzc05hbWVcbiAgICAgICl9XG4gICAgICByb2xlPVwicmFkaW9ncm91cFwiXG4gICAgPlxuICAgICAge29wdGlvbnMubWFwKG9wdCA9PiB7XG4gICAgICAgIGNvbnN0IGFjdGl2ZSA9IG9wdC52YWx1ZSA9PT0gdmFsdWVcblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxidXR0b25cbiAgICAgICAgICAgIGFyaWEtY2hlY2tlZD17YWN0aXZlfVxuICAgICAgICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgICAgICAgJ2ZvbnQtbW9uZHdlc3QgdGV4dC1kaXNwbGF5IHRyYWNraW5nLVswLjFlbV0nLFxuICAgICAgICAgICAgICAndHJhbnNpdGlvbi1jb2xvcnMgY3Vyc29yLXBvaW50ZXIgd2hpdGVzcGFjZS1ub3dyYXAnLFxuICAgICAgICAgICAgICAnYm9yZGVyLXIgYm9yZGVyLW1pZGdyb3VuZC8xNSBsYXN0OmJvcmRlci1yLTAnLFxuICAgICAgICAgICAgICAnZm9jdXMtdmlzaWJsZTpvdXRsaW5lLW5vbmUgZm9jdXMtdmlzaWJsZTpyaW5nLTEgZm9jdXMtdmlzaWJsZTpyaW5nLW1pZGdyb3VuZC8zMCcsXG4gICAgICAgICAgICAgIHNpemUgPT09ICdzbScgJiYgJ2gtNyBweC0yLjUgdGV4dC14cycsXG4gICAgICAgICAgICAgIHNpemUgPT09ICdtZCcgJiYgJ2gtOCBweC0zIHRleHQteHMnLFxuICAgICAgICAgICAgICBhY3RpdmVcbiAgICAgICAgICAgICAgICA/ICdiZy1taWRncm91bmQgdGV4dC1iYWNrZ3JvdW5kJ1xuICAgICAgICAgICAgICAgIDogJ3RleHQtdGV4dC1zZWNvbmRhcnkgaG92ZXI6YmctbWlkZ3JvdW5kLzEwIGhvdmVyOnRleHQtbWlkZ3JvdW5kJ1xuICAgICAgICAgICAgKX1cbiAgICAgICAgICAgIGtleT17b3B0LnZhbHVlfVxuICAgICAgICAgICAgb25DbGljaz17KCkgPT4gb25DaGFuZ2Uob3B0LnZhbHVlKX1cbiAgICAgICAgICAgIHJvbGU9XCJyYWRpb1wiXG4gICAgICAgICAgICB0eXBlPVwiYnV0dG9uXCJcbiAgICAgICAgICA+XG4gICAgICAgICAgICB7b3B0LmxhYmVsfVxuICAgICAgICAgIDwvYnV0dG9uPlxuICAgICAgICApXG4gICAgICB9KX1cbiAgICA8L2Rpdj5cbiAgKVxufVxuXG5leHBvcnQgZnVuY3Rpb24gRmlsdGVyR3JvdXAoeyBjaGlsZHJlbiwgY2xhc3NOYW1lLCBsYWJlbCB9OiBGaWx0ZXJHcm91cFByb3BzKSB7XG4gIHJldHVybiAoXG4gICAgPGRpdiBjbGFzc05hbWU9e2NuKCdmbGV4IGl0ZW1zLWNlbnRlciBnYXAtMicsIGNsYXNzTmFtZSl9PlxuICAgICAgPHNwYW4gY2xhc3NOYW1lPVwiZm9udC1tb25kd2VzdCB0ZXh0LWRpc3BsYXkgdGV4dC14cyB0cmFja2luZy1bMC4xMmVtXSB0ZXh0LXRleHQtdGVydGlhcnlcIj5cbiAgICAgICAge2xhYmVsfVxuICAgICAgPC9zcGFuPlxuXG4gICAgICB7Y2hpbGRyZW59XG4gICAgPC9kaXY+XG4gIClcbn1cblxuaW50ZXJmYWNlIEZpbHRlckdyb3VwUHJvcHMge1xuICBjaGlsZHJlbjogUmVhY3ROb2RlXG4gIGNsYXNzTmFtZT86IHN0cmluZ1xuICBsYWJlbDogc3RyaW5nXG59XG5cbmludGVyZmFjZSBTZWdtZW50ZWRPcHRpb248VCBleHRlbmRzIHN0cmluZz4ge1xuICBsYWJlbDogc3RyaW5nXG4gIHZhbHVlOiBUXG59XG5cbmludGVyZmFjZSBTZWdtZW50ZWRQcm9wczxUIGV4dGVuZHMgc3RyaW5nPiB7XG4gIGNsYXNzTmFtZT86IHN0cmluZ1xuICBvbkNoYW5nZTogKHZhbHVlOiBUKSA9PiB2b2lkXG4gIG9wdGlvbnM6IFNlZ21lbnRlZE9wdGlvbjxUPltdXG4gIHNpemU/OiAnbWQnIHwgJ3NtJ1xuICB2YWx1ZTogVFxufVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQXlCVSxjQTRCTixZQTVCTTtBQXJCVixTQUFTLFVBQVU7QUFFWixnQkFBUyxVQUE0QjtBQUFBLEVBQzFDO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFBQSxFQUNBLE9BQU87QUFBQSxFQUNQO0FBQ0YsR0FBc0I7QUFDcEIsU0FDRTtBQUFBLElBQUM7QUFBQTtBQUFBLE1BQ0MsV0FBVztBQUFBLFFBQ1Q7QUFBQSxRQUNBO0FBQUEsTUFDRjtBQUFBLE1BQ0EsTUFBSztBQUFBLE1BRUosa0JBQVEsSUFBSSxTQUFPO0FBQ2xCLGNBQU0sU0FBUyxJQUFJLFVBQVU7QUFFN0IsZUFDRTtBQUFBLFVBQUM7QUFBQTtBQUFBLFlBQ0MsZ0JBQWM7QUFBQSxZQUNkLFdBQVc7QUFBQSxjQUNUO0FBQUEsY0FDQTtBQUFBLGNBQ0E7QUFBQSxjQUNBO0FBQUEsY0FDQSxTQUFTLFFBQVE7QUFBQSxjQUNqQixTQUFTLFFBQVE7QUFBQSxjQUNqQixTQUNJLGlDQUNBO0FBQUEsWUFDTjtBQUFBLFlBRUEsU0FBUyxNQUFNLFNBQVMsSUFBSSxLQUFLO0FBQUEsWUFDakMsTUFBSztBQUFBLFlBQ0wsTUFBSztBQUFBLFlBRUosY0FBSTtBQUFBO0FBQUEsVUFMQSxJQUFJO0FBQUEsUUFNWDtBQUFBLE1BRUosQ0FBQztBQUFBO0FBQUEsRUFDSDtBQUVKO0FBRU8sZ0JBQVMsWUFBWSxFQUFFLFVBQVUsV0FBVyxNQUFNLEdBQXFCO0FBQzVFLFNBQ0UscUJBQUMsU0FBSSxXQUFXLEdBQUcsMkJBQTJCLFNBQVMsR0FDckQ7QUFBQSx3QkFBQyxVQUFLLFdBQVUsMkVBQ2IsaUJBQ0g7QUFBQSxJQUVDO0FBQUEsS0FDSDtBQUVKOyIsCiAgIm5hbWVzIjogW10KfQo=
