"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import { useRef } from "react";
import { AlertDialog as AlertDialogPrimitive } from "radix-ui";
import { cn } from "../../utils/index.js";
import { Button } from "./button.js";
function WarningTriangle({ className }) {
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
        /* @__PURE__ */ jsx("path", { d: "m10.29 3.86-8.16 14a2 2 0 0 0 1.73 3h16.28a2 2 0 0 0 1.73-3l-8.16-14a2 2 0 0 0-3.46 0z" }),
        /* @__PURE__ */ jsx("line", { x1: "12", x2: "12", y1: "9", y2: "13" }),
        /* @__PURE__ */ jsx("line", { x1: "12", x2: "12.01", y1: "17", y2: "17" })
      ]
    }
  );
}
export function ConfirmDialog({
  cancelLabel = "Cancel",
  confirmLabel = "Confirm",
  description,
  destructive = false,
  loading = false,
  onCancel,
  onConfirm,
  open,
  title
}) {
  const confirmedRef = useRef(false);
  return /* @__PURE__ */ jsx(
    AlertDialogPrimitive.Root,
    {
      onOpenChange: (v) => {
        if (!v && !confirmedRef.current) onCancel();
        confirmedRef.current = false;
      },
      open,
      children: /* @__PURE__ */ jsxs(AlertDialogPrimitive.Portal, { children: [
        /* @__PURE__ */ jsx(
          AlertDialogPrimitive.Overlay,
          {
            className: cn(
              "fixed inset-0 z-50",
              "bg-black/60 backdrop-blur-sm",
              "data-[state=open]:animate-in data-[state=open]:fade-in-0",
              "data-[state=closed]:animate-out data-[state=closed]:fade-out-0"
            )
          }
        ),
        /* @__PURE__ */ jsxs(
          AlertDialogPrimitive.Content,
          {
            className: cn(
              "fixed top-1/2 left-1/2 z-50 -translate-x-1/2 -translate-y-1/2",
              "w-[calc(100%-2rem)] max-w-md",
              "border border-midground/15 bg-background-base text-foreground-base shadow-lg outline-none",
              "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
              "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
              "duration-150"
            ),
            children: [
              /* @__PURE__ */ jsxs("div", { className: "flex items-start gap-3 p-4 border-b border-midground/15", children: [
                destructive && /* @__PURE__ */ jsx("div", { "aria-hidden": true, className: "mt-0.5 shrink-0 text-destructive", children: /* @__PURE__ */ jsx(WarningTriangle, { className: "h-4 w-4" }) }),
                /* @__PURE__ */ jsxs("div", { className: "flex-1 min-w-0 flex flex-col gap-1", children: [
                  /* @__PURE__ */ jsx(
                    AlertDialogPrimitive.Title,
                    {
                      className: "font-expanded text-sm font-bold tracking-[0.08em] uppercase",
                      children: title
                    }
                  ),
                  description && /* @__PURE__ */ jsx(
                    AlertDialogPrimitive.Description,
                    {
                      className: "font-mondwest text-xs text-midground/60 leading-relaxed",
                      children: description
                    }
                  )
                ] })
              ] }),
              /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-end gap-2 p-3", children: [
                /* @__PURE__ */ jsx(AlertDialogPrimitive.Cancel, { asChild: true, children: /* @__PURE__ */ jsx(Button, { disabled: loading, outlined: true, type: "button", children: cancelLabel }) }),
                /* @__PURE__ */ jsx(AlertDialogPrimitive.Action, { asChild: true, children: /* @__PURE__ */ jsx(
                  Button,
                  {
                    destructive,
                    disabled: loading,
                    onClick: () => {
                      confirmedRef.current = true;
                      onConfirm();
                    },
                    type: "button",
                    children: loading ? "\u2026" : confirmLabel
                  }
                ) })
              ] })
            ]
          }
        )
      ] })
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZVJlZiB9IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHsgQWxlcnREaWFsb2cgYXMgQWxlcnREaWFsb2dQcmltaXRpdmUgfSBmcm9tICdyYWRpeC11aSdcblxuaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcbmltcG9ydCB7IEJ1dHRvbiB9IGZyb20gJy4vYnV0dG9uJ1xuXG5mdW5jdGlvbiBXYXJuaW5nVHJpYW5nbGUoeyBjbGFzc05hbWUgfTogeyBjbGFzc05hbWU/OiBzdHJpbmcgfSkge1xuICByZXR1cm4gKFxuICAgIDxzdmdcbiAgICAgIGFyaWEtaGlkZGVuXG4gICAgICBjbGFzc05hbWU9e2NsYXNzTmFtZX1cbiAgICAgIGZpbGw9XCJub25lXCJcbiAgICAgIHN0cm9rZT1cImN1cnJlbnRDb2xvclwiXG4gICAgICBzdHJva2VMaW5lY2FwPVwicm91bmRcIlxuICAgICAgc3Ryb2tlTGluZWpvaW49XCJyb3VuZFwiXG4gICAgICBzdHJva2VXaWR0aD17Mn1cbiAgICAgIHZpZXdCb3g9XCIwIDAgMjQgMjRcIlxuICAgID5cbiAgICAgIDxwYXRoIGQ9XCJtMTAuMjkgMy44Ni04LjE2IDE0YTIgMiAwIDAgMCAxLjczIDNoMTYuMjhhMiAyIDAgMCAwIDEuNzMtM2wtOC4xNi0xNGEyIDIgMCAwIDAtMy40NiAwelwiIC8+XG4gICAgICA8bGluZSB4MT1cIjEyXCIgeDI9XCIxMlwiIHkxPVwiOVwiIHkyPVwiMTNcIiAvPlxuICAgICAgPGxpbmUgeDE9XCIxMlwiIHgyPVwiMTIuMDFcIiB5MT1cIjE3XCIgeTI9XCIxN1wiIC8+XG4gICAgPC9zdmc+XG4gIClcbn1cblxuZXhwb3J0IGZ1bmN0aW9uIENvbmZpcm1EaWFsb2coe1xuICBjYW5jZWxMYWJlbCA9ICdDYW5jZWwnLFxuICBjb25maXJtTGFiZWwgPSAnQ29uZmlybScsXG4gIGRlc2NyaXB0aW9uLFxuICBkZXN0cnVjdGl2ZSA9IGZhbHNlLFxuICBsb2FkaW5nID0gZmFsc2UsXG4gIG9uQ2FuY2VsLFxuICBvbkNvbmZpcm0sXG4gIG9wZW4sXG4gIHRpdGxlXG59OiBDb25maXJtRGlhbG9nUHJvcHMpIHtcbiAgY29uc3QgY29uZmlybWVkUmVmID0gdXNlUmVmKGZhbHNlKVxuXG4gIHJldHVybiAoXG4gICAgPEFsZXJ0RGlhbG9nUHJpbWl0aXZlLlJvb3RcbiAgICAgIG9uT3BlbkNoYW5nZT17diA9PiB7XG4gICAgICAgIGlmICghdiAmJiAhY29uZmlybWVkUmVmLmN1cnJlbnQpIG9uQ2FuY2VsKClcbiAgICAgICAgY29uZmlybWVkUmVmLmN1cnJlbnQgPSBmYWxzZVxuICAgICAgfX1cbiAgICAgIG9wZW49e29wZW59XG4gICAgPlxuICAgICAgPEFsZXJ0RGlhbG9nUHJpbWl0aXZlLlBvcnRhbD5cbiAgICAgICAgPEFsZXJ0RGlhbG9nUHJpbWl0aXZlLk92ZXJsYXlcbiAgICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICAgJ2ZpeGVkIGluc2V0LTAgei01MCcsXG4gICAgICAgICAgICAnYmctYmxhY2svNjAgYmFja2Ryb3AtYmx1ci1zbScsXG4gICAgICAgICAgICAnZGF0YS1bc3RhdGU9b3Blbl06YW5pbWF0ZS1pbiBkYXRhLVtzdGF0ZT1vcGVuXTpmYWRlLWluLTAnLFxuICAgICAgICAgICAgJ2RhdGEtW3N0YXRlPWNsb3NlZF06YW5pbWF0ZS1vdXQgZGF0YS1bc3RhdGU9Y2xvc2VkXTpmYWRlLW91dC0wJ1xuICAgICAgICAgICl9XG4gICAgICAgIC8+XG5cbiAgICAgICAgPEFsZXJ0RGlhbG9nUHJpbWl0aXZlLkNvbnRlbnRcbiAgICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICAgJ2ZpeGVkIHRvcC0xLzIgbGVmdC0xLzIgei01MCAtdHJhbnNsYXRlLXgtMS8yIC10cmFuc2xhdGUteS0xLzInLFxuICAgICAgICAgICAgJ3ctW2NhbGMoMTAwJS0ycmVtKV0gbWF4LXctbWQnLFxuICAgICAgICAgICAgJ2JvcmRlciBib3JkZXItbWlkZ3JvdW5kLzE1IGJnLWJhY2tncm91bmQtYmFzZSB0ZXh0LWZvcmVncm91bmQtYmFzZSBzaGFkb3ctbGcgb3V0bGluZS1ub25lJyxcbiAgICAgICAgICAgICdkYXRhLVtzdGF0ZT1vcGVuXTphbmltYXRlLWluIGRhdGEtW3N0YXRlPW9wZW5dOmZhZGUtaW4tMCBkYXRhLVtzdGF0ZT1vcGVuXTp6b29tLWluLTk1JyxcbiAgICAgICAgICAgICdkYXRhLVtzdGF0ZT1jbG9zZWRdOmFuaW1hdGUtb3V0IGRhdGEtW3N0YXRlPWNsb3NlZF06ZmFkZS1vdXQtMCBkYXRhLVtzdGF0ZT1jbG9zZWRdOnpvb20tb3V0LTk1JyxcbiAgICAgICAgICAgICdkdXJhdGlvbi0xNTAnXG4gICAgICAgICAgKX1cbiAgICAgICAgPlxuICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBpdGVtcy1zdGFydCBnYXAtMyBwLTQgYm9yZGVyLWIgYm9yZGVyLW1pZGdyb3VuZC8xNVwiPlxuICAgICAgICAgICAge2Rlc3RydWN0aXZlICYmIChcbiAgICAgICAgICAgICAgPGRpdiBhcmlhLWhpZGRlbiBjbGFzc05hbWU9XCJtdC0wLjUgc2hyaW5rLTAgdGV4dC1kZXN0cnVjdGl2ZVwiPlxuICAgICAgICAgICAgICAgIDxXYXJuaW5nVHJpYW5nbGUgY2xhc3NOYW1lPVwiaC00IHctNFwiIC8+XG4gICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgKX1cblxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4LTEgbWluLXctMCBmbGV4IGZsZXgtY29sIGdhcC0xXCI+XG4gICAgICAgICAgICAgIDxBbGVydERpYWxvZ1ByaW1pdGl2ZS5UaXRsZVxuICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cImZvbnQtZXhwYW5kZWQgdGV4dC1zbSBmb250LWJvbGQgdHJhY2tpbmctWzAuMDhlbV0gdXBwZXJjYXNlXCJcbiAgICAgICAgICAgICAgPlxuICAgICAgICAgICAgICAgIHt0aXRsZX1cbiAgICAgICAgICAgICAgPC9BbGVydERpYWxvZ1ByaW1pdGl2ZS5UaXRsZT5cblxuICAgICAgICAgICAgICB7ZGVzY3JpcHRpb24gJiYgKFxuICAgICAgICAgICAgICAgIDxBbGVydERpYWxvZ1ByaW1pdGl2ZS5EZXNjcmlwdGlvblxuICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwiZm9udC1tb25kd2VzdCB0ZXh0LXhzIHRleHQtbWlkZ3JvdW5kLzYwIGxlYWRpbmctcmVsYXhlZFwiXG4gICAgICAgICAgICAgICAgPlxuICAgICAgICAgICAgICAgICAge2Rlc2NyaXB0aW9ufVxuICAgICAgICAgICAgICAgIDwvQWxlcnREaWFsb2dQcmltaXRpdmUuRGVzY3JpcHRpb24+XG4gICAgICAgICAgICAgICl9XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICA8L2Rpdj5cblxuICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBpdGVtcy1jZW50ZXIganVzdGlmeS1lbmQgZ2FwLTIgcC0zXCI+XG4gICAgICAgICAgICA8QWxlcnREaWFsb2dQcmltaXRpdmUuQ2FuY2VsIGFzQ2hpbGQ+XG4gICAgICAgICAgICAgIDxCdXR0b24gZGlzYWJsZWQ9e2xvYWRpbmd9IG91dGxpbmVkIHR5cGU9XCJidXR0b25cIj5cbiAgICAgICAgICAgICAgICB7Y2FuY2VsTGFiZWx9XG4gICAgICAgICAgICAgIDwvQnV0dG9uPlxuICAgICAgICAgICAgPC9BbGVydERpYWxvZ1ByaW1pdGl2ZS5DYW5jZWw+XG5cbiAgICAgICAgICAgIDxBbGVydERpYWxvZ1ByaW1pdGl2ZS5BY3Rpb24gYXNDaGlsZD5cbiAgICAgICAgICAgICAgPEJ1dHRvblxuICAgICAgICAgICAgICAgIGRlc3RydWN0aXZlPXtkZXN0cnVjdGl2ZX1cbiAgICAgICAgICAgICAgICBkaXNhYmxlZD17bG9hZGluZ31cbiAgICAgICAgICAgICAgICBvbkNsaWNrPXsoKSA9PiB7XG4gICAgICAgICAgICAgICAgICBjb25maXJtZWRSZWYuY3VycmVudCA9IHRydWVcbiAgICAgICAgICAgICAgICAgIG9uQ29uZmlybSgpXG4gICAgICAgICAgICAgICAgfX1cbiAgICAgICAgICAgICAgICB0eXBlPVwiYnV0dG9uXCJcbiAgICAgICAgICAgICAgPlxuICAgICAgICAgICAgICAgIHtsb2FkaW5nID8gJ1x1MjAyNicgOiBjb25maXJtTGFiZWx9XG4gICAgICAgICAgICAgIDwvQnV0dG9uPlxuICAgICAgICAgICAgPC9BbGVydERpYWxvZ1ByaW1pdGl2ZS5BY3Rpb24+XG4gICAgICAgICAgPC9kaXY+XG4gICAgICAgIDwvQWxlcnREaWFsb2dQcmltaXRpdmUuQ29udGVudD5cbiAgICAgIDwvQWxlcnREaWFsb2dQcmltaXRpdmUuUG9ydGFsPlxuICAgIDwvQWxlcnREaWFsb2dQcmltaXRpdmUuUm9vdD5cbiAgKVxufVxuXG5pbnRlcmZhY2UgQ29uZmlybURpYWxvZ1Byb3BzIHtcbiAgY2FuY2VsTGFiZWw/OiBzdHJpbmdcbiAgY29uZmlybUxhYmVsPzogc3RyaW5nXG4gIGRlc2NyaXB0aW9uPzogc3RyaW5nXG4gIGRlc3RydWN0aXZlPzogYm9vbGVhblxuICBsb2FkaW5nPzogYm9vbGVhblxuICBvbkNhbmNlbDogKCkgPT4gdm9pZFxuICBvbkNvbmZpcm06ICgpID0+IHZvaWRcbiAgb3BlbjogYm9vbGVhblxuICB0aXRsZTogc3RyaW5nXG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBVUksU0FVRSxLQVZGO0FBUkosU0FBUyxjQUFjO0FBQ3ZCLFNBQVMsZUFBZSw0QkFBNEI7QUFFcEQsU0FBUyxVQUFVO0FBQ25CLFNBQVMsY0FBYztBQUV2QixTQUFTLGdCQUFnQixFQUFFLFVBQVUsR0FBMkI7QUFDOUQsU0FDRTtBQUFBLElBQUM7QUFBQTtBQUFBLE1BQ0MsZUFBVztBQUFBLE1BQ1g7QUFBQSxNQUNBLE1BQUs7QUFBQSxNQUNMLFFBQU87QUFBQSxNQUNQLGVBQWM7QUFBQSxNQUNkLGdCQUFlO0FBQUEsTUFDZixh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
