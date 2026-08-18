"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import { Dialog as DialogPrimitive } from "radix-ui";
import { cn } from "../../utils/index.js";
function Dialog({ ...props }) {
  return /* @__PURE__ */ jsx(DialogPrimitive.Root, { "data-slot": "dialog", ...props });
}
function DialogTrigger({ ...props }) {
  return /* @__PURE__ */ jsx(DialogPrimitive.Trigger, { "data-slot": "dialog-trigger", ...props });
}
function DialogPortal({ ...props }) {
  return /* @__PURE__ */ jsx(DialogPrimitive.Portal, { "data-slot": "dialog-portal", ...props });
}
function DialogClose({ ...props }) {
  return /* @__PURE__ */ jsx(DialogPrimitive.Close, { "data-slot": "dialog-close", ...props });
}
function DialogOverlay({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    DialogPrimitive.Overlay,
    {
      className: cn(
        "fixed inset-0 z-50",
        "bg-black/60 backdrop-blur-sm",
        "data-[state=open]:animate-in data-[state=open]:fade-in-0",
        "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
        className
      ),
      "data-slot": "dialog-overlay",
      ...props
    }
  );
}
function DialogContent({
  className,
  children,
  showCloseButton = true,
  ...props
}) {
  return /* @__PURE__ */ jsxs(DialogPortal, { children: [
    /* @__PURE__ */ jsx(DialogOverlay, {}),
    /* @__PURE__ */ jsxs(
      DialogPrimitive.Content,
      {
        className: cn(
          "fixed top-1/2 left-1/2 z-50 -translate-x-1/2 -translate-y-1/2",
          "grid w-full max-w-md gap-0",
          "border border-midground/15 bg-background-base text-foreground-base shadow-lg outline-none",
          "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
          "duration-150",
          className
        ),
        "data-slot": "dialog-content",
        ...props,
        children: [
          children,
          showCloseButton && /* @__PURE__ */ jsxs(
            DialogPrimitive.Close,
            {
              className: cn(
                "absolute top-3 right-3",
                "flex h-6 w-6 items-center justify-center",
                "text-midground/50 transition-colors hover:text-midground",
                "focus:outline-none focus-visible:ring-1 focus-visible:ring-midground/30",
                "disabled:pointer-events-none"
              ),
              "data-slot": "dialog-close",
              children: [
                /* @__PURE__ */ jsx(XIcon, { className: "h-3.5 w-3.5" }),
                /* @__PURE__ */ jsx("span", { className: "sr-only", children: "Close" })
              ]
            }
          )
        ]
      }
    )
  ] });
}
function DialogHeader({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "flex flex-col gap-1 p-4 border-b border-midground/15",
        className
      ),
      "data-slot": "dialog-header",
      ...props
    }
  );
}
function DialogFooter({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "flex items-center justify-end gap-2 p-3",
        className
      ),
      "data-slot": "dialog-footer",
      ...props
    }
  );
}
function DialogTitle({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    DialogPrimitive.Title,
    {
      className: cn(
        "font-expanded text-sm font-bold tracking-[0.08em] uppercase",
        className
      ),
      "data-slot": "dialog-title",
      ...props
    }
  );
}
function DialogDescription({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    DialogPrimitive.Description,
    {
      className: cn(
        "font-mondwest text-xs text-midground/60 leading-relaxed",
        className
      ),
      "data-slot": "dialog-description",
      ...props
    }
  );
}
function XIcon({ className }) {
  return /* @__PURE__ */ jsxs(
    "svg",
    {
      "aria-hidden": true,
      className,
      fill: "none",
      stroke: "currentColor",
      strokeLinecap: "round",
      strokeLinejoin: "round",
      strokeWidth: 2,
      viewBox: "0 0 24 24",
      children: [
        /* @__PURE__ */ jsx("line", { x1: "18", x2: "6", y1: "6", y2: "18" }),
        /* @__PURE__ */ jsx("line", { x1: "6", x2: "18", y1: "6", y2: "18" })
      ]
    }
  );
}
export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCAqIGFzIFJlYWN0IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHsgRGlhbG9nIGFzIERpYWxvZ1ByaW1pdGl2ZSB9IGZyb20gJ3JhZGl4LXVpJ1xuXG5pbXBvcnQgeyBjbiB9IGZyb20gJy4uLy4uL3V0aWxzJ1xuXG5mdW5jdGlvbiBEaWFsb2coeyAuLi5wcm9wcyB9OiBSZWFjdC5Db21wb25lbnRQcm9wczx0eXBlb2YgRGlhbG9nUHJpbWl0aXZlLlJvb3Q+KSB7XG4gIHJldHVybiA8RGlhbG9nUHJpbWl0aXZlLlJvb3QgZGF0YS1zbG90PVwiZGlhbG9nXCIgey4uLnByb3BzfSAvPlxufVxuXG5mdW5jdGlvbiBEaWFsb2dUcmlnZ2VyKHsgLi4ucHJvcHMgfTogUmVhY3QuQ29tcG9uZW50UHJvcHM8dHlwZW9mIERpYWxvZ1ByaW1pdGl2ZS5UcmlnZ2VyPikge1xuICByZXR1cm4gPERpYWxvZ1ByaW1pdGl2ZS5UcmlnZ2VyIGRhdGEtc2xvdD1cImRpYWxvZy10cmlnZ2VyXCIgey4uLnByb3BzfSAvPlxufVxuXG5mdW5jdGlvbiBEaWFsb2dQb3J0YWwoeyAuLi5wcm9wcyB9OiBSZWFjdC5Db21wb25lbnRQcm9wczx0eXBlb2YgRGlhbG9nUHJpbWl0aXZlLlBvcnRhbD4pIHtcbiAgcmV0dXJuIDxEaWFsb2dQcmltaXRpdmUuUG9ydGFsIGRhdGEtc2xvdD1cImRpYWxvZy1wb3J0YWxcIiB7Li4ucHJvcHN9IC8+XG59XG5cbmZ1bmN0aW9uIERpYWxvZ0Nsb3NlKHsgLi4ucHJvcHMgfTogUmVhY3QuQ29tcG9uZW50UHJvcHM8dHlwZW9mIERpYWxvZ1ByaW1pdGl2ZS5DbG9zZT4pIHtcbiAgcmV0dXJuIDxEaWFsb2dQcmltaXRpdmUuQ2xvc2UgZGF0YS1zbG90PVwiZGlhbG9nLWNsb3NlXCIgey4uLnByb3BzfSAvPlxufVxuXG5mdW5jdGlvbiBEaWFsb2dPdmVybGF5KHtcbiAgY2xhc3NOYW1lLFxuICAuLi5wcm9wc1xufTogUmVhY3QuQ29tcG9uZW50UHJvcHM8dHlwZW9mIERpYWxvZ1ByaW1pdGl2ZS5PdmVybGF5Pikge1xuICByZXR1cm4gKFxuICAgIDxEaWFsb2dQcmltaXRpdmUuT3ZlcmxheVxuICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgJ2ZpeGVkIGluc2V0LTAgei01MCcsXG4gICAgICAgICdiZy1ibGFjay82MCBiYWNrZHJvcC1ibHVyLXNtJyxcbiAgICAgICAgJ2RhdGEtW3N0YXRlPW9wZW5dOmFuaW1hdGUtaW4gZGF0YS1bc3RhdGU9b3Blbl06ZmFkZS1pbi0wJyxcbiAgICAgICAgJ2RhdGEtW3N0YXRlPWNsb3NlZF06YW5pbWF0ZS1vdXQgZGF0YS1bc3RhdGU9Y2xvc2VkXTpmYWRlLW91dC0wJyxcbiAgICAgICAgY2xhc3NOYW1lXG4gICAgICApfVxuICAgICAgZGF0YS1zbG90PVwiZGlhbG9nLW92ZXJsYXlcIlxuICAgICAgey4uLnByb3BzfVxuICAgIC8+XG4gIClcbn1cblxuZnVuY3Rpb24gRGlhbG9nQ29udGVudCh7XG4gIGNsYXNzTmFtZSxcbiAgY2hpbGRyZW4sXG4gIHNob3dDbG9zZUJ1dHRvbiA9IHRydWUsXG4gIC4uLnByb3BzXG59OiBSZWFjdC5Db21wb25lbnRQcm9wczx0eXBlb2YgRGlhbG9nUHJpbWl0aXZlLkNvbnRlbnQ+ICYge1xuICBzaG93Q2xvc2VCdXR0b24/OiBib29sZWFuXG59KSB7XG4gIHJldHVybiAoXG4gICAgPERpYWxvZ1BvcnRhbD5cbiAgICAgIDxEaWFsb2dPdmVybGF5IC8+XG5cbiAgICAgIDxEaWFsb2dQcmltaXRpdmUuQ29udGVudFxuICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICdmaXhlZCB0b3AtMS8yIGxlZnQtMS8yIHotNTAgLXRyYW5zbGF0ZS14LTEvMiAtdHJhbnNsYXRlLXktMS8yJyxcbiAgICAgICAgICAnZ3JpZCB3LWZ1bGwgbWF4LXctbWQgZ2FwLTAnLFxuICAgICAgICAgICdib3JkZXIgYm9yZGVyLW1pZGdyb3VuZC8xNSBiZy1iYWNrZ3JvdW5kLWJhc2UgdGV4dC1mb3JlZ3JvdW5kLWJhc2Ugc2hhZG93LWxnIG91dGxpbmUtbm9uZScsXG4gICAgICAgICAgJ2RhdGEtW3N0YXRlPW9wZW5dOmFuaW1hdGUtaW4gZGF0YS1bc3RhdGU9b3Blbl06ZmFkZS1pbi0wIGRhdGEtW3N0YXRlPW9wZW5dOnpvb20taW4tOTUnLFxuICAgICAgICAgICdkYXRhLVtzdGF0ZT1jbG9zZWRdOmFuaW1hdGUtb3V0IGRhdGEtW3N0YXRlPWNsb3NlZF06ZmFkZS1vdXQtMCBkYXRhLVtzdGF0ZT1jbG9zZWRdOnpvb20tb3V0LTk1JyxcbiAgICAgICAgICAnZHVyYXRpb24tMTUwJyxcbiAgICAgICAgICBjbGFzc05hbWVcbiAgICAgICAgKX1cbiAgICAgICAgZGF0YS1zbG90PVwiZGlhbG9nLWNvbnRlbnRcIlxuICAgICAgICB7Li4ucHJvcHN9XG4gICAgICA+XG4gICAgICAgIHtjaGlsZHJlbn1cblxuICAgICAgICB7c2hvd0Nsb3NlQnV0dG9uICYmIChcbiAgICAgICAgICA8RGlhbG9nUHJpbWl0aXZlLkNsb3NlXG4gICAgICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICAgICAnYWJzb2x1dGUgdG9wLTMgcmlnaHQtMycsXG4gICAgICAgICAgICAgICdmbGV4IGgtNiB3LTYgaXRlbXMtY2VudGVyIGp1c3RpZnktY2VudGVyJyxcbiAgICAgICAgICAgICAgJ3RleHQtbWlkZ3JvdW5kLzUwIHRyYW5zaXRpb24tY29sb3JzIGhvdmVyOnRleHQtbWlkZ3JvdW5kJyxcbiAgICAgICAgICAgICAgJ2ZvY3VzOm91dGxpbmUtbm9uZSBmb2N1cy12aXNpYmxlOnJpbmctMSBmb2N1cy12aXNpYmxlOnJpbmctbWlkZ3JvdW5kLzMwJyxcbiAgICAgICAgICAgICAgJ2Rpc2FibGVkOnBvaW50ZXItZXZlbnRzLW5vbmUnXG4gICAgICAgICAgICApfVxuICAgICAgICAgICAgZGF0YS1zbG90PVwiZGlhbG9nLWNsb3NlXCJcbiAgICAgICAgICA+XG4gICAgICAgICAgICA8WEljb24gY2xhc3NOYW1lPVwiaC0zLjUgdy0zLjVcIiAvPlxuICAgICAgICAgICAgPHNwYW4gY2xhc3NOYW1lPVwic3Itb25seVwiPkNsb3NlPC9zcGFuPlxuICAgICAgICAgIDwvRGlhbG9nUHJpbWl0aXZlLkNsb3NlPlxuICAgICAgICApfVxuICAgICAgPC9EaWFsb2dQcmltaXRpdmUuQ29udGVudD5cbiAgICA8L0RpYWxvZ1BvcnRhbD5cbiAgKVxufVxuXG5mdW5jdGlvbiBEaWFsb2dIZWFkZXIoeyBjbGFzc05hbWUsIC4uLnByb3BzIH06IFJlYWN0LkNvbXBvbmVudFByb3BzPCdkaXYnPikge1xuICByZXR1cm4gKFxuICAgIDxkaXZcbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICdmbGV4IGZsZXgtY29sIGdhcC0xIHAtNCBib3JkZXItYiBib3JkZXItbWlkZ3JvdW5kLzE1JyxcbiAgICAgICAgY2xhc3NOYW1lXG4gICAgICApfVxuICAgICAgZGF0YS1zbG90PVwiZGlhbG9nLWhlYWRlclwiXG4gICAgICB7Li4ucHJvcHN9XG4gICAgLz5cbiAgKVxufVxuXG5mdW5jdGlvbiBEaWFsb2dGb290ZXIoeyBjbGFzc05hbWUsIC4uLnByb3BzIH06IFJlYWN0LkNvbXBvbmVudFByb3BzPCdkaXYnPikge1xuICByZXR1cm4gKFxuICAgIDxkaXZcbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICdmbGV4IGl0ZW1zLWNlbnRlciBqdXN0aWZ5LWVuZCBnYXAtMiBwLTMnLFxuICAgICAgICBjbGFzc05hbWVcbiAgICAgICl9XG4gICAgICBkYXRhLXNsb3Q9XCJkaWFsb2ctZm9vdGVyXCJcbiAgICAgIHsuLi5wcm9wc31cbiAgICAvPlxuICApXG59XG5cbmZ1bmN0aW9uIERpYWxvZ1RpdGxlKHtcbiAgY2xhc3NOYW1lLFxuICAuLi5wcm9wc1xufTogUmVhY3QuQ29tcG9uZW50UHJvcHM8dHlwZW9mIERpYWxvZ1ByaW1pdGl2ZS5UaXRsZT4pIHtcbiAgcmV0dXJuIChcbiAgICA8RGlhbG9nUHJpbWl0aXZlLlRpdGxlXG4gICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAnZm9udC1leHBhbmRlZCB0ZXh0LXNtIGZvbnQtYm9sZCB0cmFja2luZy1bMC4wOGVtXSB1cHBlcmNhc2UnLFxuICAgICAgICBjbGFzc05hbWVcbiAgICAgICl9XG4gICAgICBkYXRhLXNsb3Q9XCJkaWFsb2ctdGl0bGVcIlxuICAgICAgey4uLnByb3BzfVxuICAgIC8+XG4gIClcbn1cblxuZnVuY3Rpb24gRGlhbG9nRGVzY3JpcHRpb24oe1xuICBjbGFzc05hbWUsXG4gIC4uLnByb3BzXG59OiBSZWFjdC5Db21wb25lbnRQcm9wczx0eXBlb2YgRGlhbG9nUHJpbWl0aXZlLkRlc2NyaXB0aW9uPikge1xuICByZXR1cm4gKFxuICAgIDxEaWFsb2dQcmltaXRpdmUuRGVzY3JpcHRpb25cbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICdmb250LW1vbmR3ZXN0IHRleHQteHMgdGV4dC1taWRncm91bmQvNjAgbGVhZGluZy1yZWxheGVkJyxcbiAgICAgICAgY2xhc3NOYW1lXG4gICAgICApfVxuICAgICAgZGF0YS1zbG90PVwiZGlhbG9nLWRlc2NyaXB0aW9uXCJcbiAgICAgIHsuLi5wcm9wc31cbiAgICAvPlxuICApXG59XG5cbmZ1bmN0aW9uIFhJY29uKHsgY2xhc3NOYW1lIH06IHsgY2xhc3NOYW1lPzogc3RyaW5nIH0pIHtcbiAgcmV0dXJuIChcbiAgICA8c3ZnXG4gICAgICBhcmlhLWhpZGRlblxuICAgICAgY2xhc3NOYW1lPXtjbGFzc05hbWV9XG4gICAgICBmaWxsPVwibm9uZVwiXG4gICAgICBzdHJva2U9XCJjdXJyZW50Q29sb3JcIlxuICAgICAgc3Ryb2tlTGluZWNhcD1cInJvdW5kXCJcbiAgICAgIHN0cm9rZUxpbmVqb2luPVwicm91bmRcIlxuICAgICAgc3Ryb2tlV2lkdGg9ezJ9XG4gICAgICB2aWV3Qm94PVwiMCAwIDI0IDI0XCJcbiAgICA+XG4gICAgICA8bGluZSB4MT1cIjE4XCIgeDI9XCI2XCIgeTE9XCI2XCIgeTI9XCIxOFwiIC8+XG4gICAgICA8bGluZSB4MT1cIjZcIiB4Mj1cIjE4XCIgeTE9XCI2XCIgeTI9XCIxOFwiIC8+XG4gICAgPC9zdmc+XG4gIClcbn1cblxuZXhwb3J0IHtcbiAgRGlhbG9nLFxuICBEaWFsb2dDbG9zZSxcbiAgRGlhbG9nQ29udGVudCxcbiAgRGlhbG9nRGVzY3JpcHRpb24sXG4gIERpYWxvZ0Zvb3RlcixcbiAgRGlhbG9nSGVhZGVyLFxuICBEaWFsb2dPdmVybGF5LFxuICBEaWFsb2dQb3J0YWwsXG4gIERpYWxvZ1RpdGxlLFxuICBEaWFsb2dUcmlnZ2VyXG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBUVMsY0E4REMsWUE5REQ7QUFMVCxTQUFTLFVBQVUsdUJBQXVCO0FBRTFDLFNBQVMsVUFBVTtBQUVuQixTQUFTLE9BQU8sRUFBRSxHQUFHLE1BQU0sR0FBc0Q7QUFDL0UsU0FBTyxvQkFBQyxnQkFBZ0IsTUFBaEIsRUFBcUIsYUFBVSxVQUFVLEdBQUcsT0FBTztBQUM3RDtBQUVBLFNBQVMsY0FBYyxFQUFFLEdBQUcsTUFBTSxHQUF5RDtBQUN6RixTQUFPLG9CQUFDLGdCQUFnQixTQUFoQixFQUF3QixhQUFVLGtCQUFrQixHQUFHLE9BQU87QUFDeEU7QUFFQSxTQUFTLGFBQWEsRUFBRSxHQUFHLE1BQU0sR0FBd0Q7QUFDdkYsU0FBTyxvQkFBQyxnQkFBZ0IsUUFBaEIsRUFBdUIsYUFBVSxpQkFBaUIsR0FBRyxPQUFPO0FBQ3RFO0FBRUEsU0FBUyxZQUFZLEVBQUUsR0FBRyxNQUFNLEdBQXVEO0FBQ3JGLFNBQU8sb0JBQUMsZ0JBQWdCLE9BQWhCLEVBQXNCLGFBQVUsZ0JBQWdCLEdBQUcsT0FBTztBQUNwRTtBQUVBLFNBQVMsY0FBYztBQUFBLEVBQ3JCO0FBQUEsRUFDQSxHQUFHO0FBQ0wsR0FBeUQ7QUFDdkQsU0FDRTtBQUFBLElBQUMsZ0JBQWdCO0FBQUEsSUFBaEI7QUFBQSxNQUNDLFdB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
