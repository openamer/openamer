"use client";
import { jsx } from "react/jsx-runtime";
import { forwardRef } from "react";
import { Checkbox as CheckboxPrimitive } from "radix-ui";
import { cn } from "../../utils/index.js";
import { CheckIcon } from "./icons/check.js";
export const Checkbox = forwardRef(function Checkbox2({ className, ...props }, ref) {
  return /* @__PURE__ */ jsx(
    CheckboxPrimitive.Root,
    {
      className: cn(
        "peer flex h-4 w-4 shrink-0 cursor-pointer items-center justify-center border transition-colors outline-none",
        "focus-visible:ring-1 focus-visible:ring-midground/30",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "data-[state=unchecked]:border-midground/20 data-[state=unchecked]:bg-background",
        "data-[state=unchecked]:hover:border-midground/30",
        "data-[state=checked]:border-midground/30 data-[state=checked]:bg-midground/15",
        "data-[state=indeterminate]:border-midground/30 data-[state=indeterminate]:bg-midground/15",
        className
      ),
      ref,
      ...props,
      children: /* @__PURE__ */ jsx(CheckboxPrimitive.Indicator, { className: "flex items-center justify-center text-current", children: /* @__PURE__ */ jsx(CheckIcon, { className: "h-3 w-3 text-midground" }) })
    }
  );
});
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IGZvcndhcmRSZWYsIHR5cGUgQ29tcG9uZW50UHJvcHNXaXRob3V0UmVmLCB0eXBlIEVsZW1lbnRSZWYgfSBmcm9tICdyZWFjdCdcbmltcG9ydCB7IENoZWNrYm94IGFzIENoZWNrYm94UHJpbWl0aXZlIH0gZnJvbSAncmFkaXgtdWknXG5cbmltcG9ydCB7IGNuIH0gZnJvbSAnLi4vLi4vdXRpbHMnXG5cbmltcG9ydCB7IENoZWNrSWNvbiB9IGZyb20gJy4vaWNvbnMvY2hlY2snXG5cbmV4cG9ydCBjb25zdCBDaGVja2JveCA9IGZvcndhcmRSZWY8XG4gIEVsZW1lbnRSZWY8dHlwZW9mIENoZWNrYm94UHJpbWl0aXZlLlJvb3Q+LFxuICBDaGVja2JveFByb3BzXG4+KGZ1bmN0aW9uIENoZWNrYm94KHsgY2xhc3NOYW1lLCAuLi5wcm9wcyB9LCByZWYpIHtcbiAgcmV0dXJuIChcbiAgICA8Q2hlY2tib3hQcmltaXRpdmUuUm9vdFxuICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgJ3BlZXIgZmxleCBoLTQgdy00IHNocmluay0wIGN1cnNvci1wb2ludGVyIGl0ZW1zLWNlbnRlciBqdXN0aWZ5LWNlbnRlciBib3JkZXIgdHJhbnNpdGlvbi1jb2xvcnMgb3V0bGluZS1ub25lJyxcbiAgICAgICAgJ2ZvY3VzLXZpc2libGU6cmluZy0xIGZvY3VzLXZpc2libGU6cmluZy1taWRncm91bmQvMzAnLFxuICAgICAgICAnZGlzYWJsZWQ6Y3Vyc29yLW5vdC1hbGxvd2VkIGRpc2FibGVkOm9wYWNpdHktNTAnLFxuICAgICAgICAnZGF0YS1bc3RhdGU9dW5jaGVja2VkXTpib3JkZXItbWlkZ3JvdW5kLzIwIGRhdGEtW3N0YXRlPXVuY2hlY2tlZF06YmctYmFja2dyb3VuZCcsXG4gICAgICAgICdkYXRhLVtzdGF0ZT11bmNoZWNrZWRdOmhvdmVyOmJvcmRlci1taWRncm91bmQvMzAnLFxuICAgICAgICAnZGF0YS1bc3RhdGU9Y2hlY2tlZF06Ym9yZGVyLW1pZGdyb3VuZC8zMCBkYXRhLVtzdGF0ZT1jaGVja2VkXTpiZy1taWRncm91bmQvMTUnLFxuICAgICAgICAnZGF0YS1bc3RhdGU9aW5kZXRlcm1pbmF0ZV06Ym9yZGVyLW1pZGdyb3VuZC8zMCBkYXRhLVtzdGF0ZT1pbmRldGVybWluYXRlXTpiZy1taWRncm91bmQvMTUnLFxuICAgICAgICBjbGFzc05hbWVcbiAgICAgICl9XG4gICAgICByZWY9e3JlZn1cbiAgICAgIHsuLi5wcm9wc31cbiAgICA+XG4gICAgICA8Q2hlY2tib3hQcmltaXRpdmUuSW5kaWNhdG9yIGNsYXNzTmFtZT1cImZsZXggaXRlbXMtY2VudGVyIGp1c3RpZnktY2VudGVyIHRleHQtY3VycmVudFwiPlxuICAgICAgICA8Q2hlY2tJY29uIGNsYXNzTmFtZT1cImgtMyB3LTMgdGV4dC1taWRncm91bmRcIiAvPlxuICAgICAgPC9DaGVja2JveFByaW1pdGl2ZS5JbmRpY2F0b3I+XG4gICAgPC9DaGVja2JveFByaW1pdGl2ZS5Sb290PlxuICApXG59KVxuXG50eXBlIENoZWNrYm94UHJvcHMgPSBDb21wb25lbnRQcm9wc1dpdGhvdXRSZWY8dHlwZW9mIENoZWNrYm94UHJpbWl0aXZlLlJvb3Q+XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBNkJRO0FBM0JSLFNBQVMsa0JBQWtFO0FBQzNFLFNBQVMsWUFBWSx5QkFBeUI7QUFFOUMsU0FBUyxVQUFVO0FBRW5CLFNBQVMsaUJBQWlCO0FBRW5CLGFBQU0sV0FBVyxXQUd0QixTQUFTQSxVQUFTLEVBQUUsV0FBVyxHQUFHLE1BQU0sR0FBRyxLQUFLO0FBQ2hELFNBQ0U7QUFBQSxJQUFDLGtCQUFrQjtBQUFBLElBQWxCO0FBQUEsTUFDQyxXQUFXO0FBQUEsUUFDVDtBQUFBLFFBQ0E7QUFBQSxRQUNBO0FBQUEsUUFDQTtBQUFBLFFBQ0E7QUFBQSxRQUNBO0FBQUEsUUFDQTtBQUFBLFFBQ0E7QUFBQSxNQUNGO0FBQUEsTUFDQTtBQUFBLE1BQ0MsR0FBRztBQUFBLE1BRUosOEJBQUMsa0JBQWtCLFdBQWxCLEVBQTRCLFdBQVUsaURBQ3JDLDhCQUFDLGFBQVUsV0FBVSwwQkFBeUIsR0FDaEQ7QUFBQTtBQUFBLEVBQ0Y7QUFFSixDQUFDOyIsCiAgIm5hbWVzIjogWyJDaGVja2JveCJdCn0K
