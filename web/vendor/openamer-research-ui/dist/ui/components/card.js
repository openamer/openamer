import { jsx } from "react/jsx-runtime";
import { cn } from "../../utils/index.js";
const CARD_STYLE = {
  background: "var(--component-card-background)",
  borderImage: "var(--component-card-border-image)",
  boxShadow: "var(--component-card-box-shadow)",
  clipPath: "var(--component-card-clip-path)"
};
export function Card({
  className,
  style,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "border border-midground/15 bg-background-base/80 text-midground w-full",
        className
      ),
      style: { ...CARD_STYLE, ...style },
      ...props
    }
  );
}
export function CardHeader({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "flex flex-col gap-1.5 p-4 border-b border-midground/15",
        className
      ),
      ...props
    }
  );
}
export function CardTitle({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    "h3",
    {
      className: cn(
        "font-expanded text-sm font-bold tracking-[0.08em] uppercase",
        className
      ),
      ...props
    }
  );
}
export function CardDescription({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    "p",
    {
      className: cn("font-mondwest text-xs text-midground/60", className),
      ...props
    }
  );
}
export function CardContent({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx("div", { className: cn("p-4", className), ...props });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuLyoqXG4gKiBUaGVtZWFibGUgY2FyZCBwcmltaXRpdmUuIFRoZW1lcyBjYW4gcmVzdHlsZSBldmVyeSBjYXJkIGJ5IHNldHRpbmcgQ1NTXG4gKiBjdXN0b20gcHJvcGVydGllczpcbiAqXG4gKiAgIC0tY29tcG9uZW50LWNhcmQtY2xpcC1wYXRoXG4gKiAgIC0tY29tcG9uZW50LWNhcmQtYm9yZGVyLWltYWdlXG4gKiAgIC0tY29tcG9uZW50LWNhcmQtYmFja2dyb3VuZFxuICogICAtLWNvbXBvbmVudC1jYXJkLWJveC1zaGFkb3dcbiAqXG4gKiBBbGwgYXJlIG9wdGlvbmFsIFx1MjAxNCB1bnNldCB2YXJzIGNvbXB1dGUgdG8gdGhlaXIgQ1NTIGluaXRpYWwgdmFsdWUuXG4gKi9cbmNvbnN0IENBUkRfU1RZTEU6IFJlYWN0LkNTU1Byb3BlcnRpZXMgPSB7XG4gIGJhY2tncm91bmQ6ICd2YXIoLS1jb21wb25lbnQtY2FyZC1iYWNrZ3JvdW5kKScsXG4gIGJvcmRlckltYWdlOiAndmFyKC0tY29tcG9uZW50LWNhcmQtYm9yZGVyLWltYWdlKScsXG4gIGJveFNoYWRvdzogJ3ZhcigtLWNvbXBvbmVudC1jYXJkLWJveC1zaGFkb3cpJyxcbiAgY2xpcFBhdGg6ICd2YXIoLS1jb21wb25lbnQtY2FyZC1jbGlwLXBhdGgpJ1xufVxuXG5leHBvcnQgZnVuY3Rpb24gQ2FyZCh7XG4gIGNsYXNzTmFtZSxcbiAgc3R5bGUsXG4gIC4uLnByb3BzXG59OiBSZWFjdC5IVE1MQXR0cmlidXRlczxIVE1MRGl2RWxlbWVudD4pIHtcbiAgcmV0dXJuIChcbiAgICA8ZGl2XG4gICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAnYm9yZGVyIGJvcmRlci1taWRncm91bmQvMTUgYmctYmFja2dyb3VuZC1iYXNlLzgwIHRleHQtbWlkZ3JvdW5kIHctZnVsbCcsXG4gICAgICAgIGNsYXNzTmFtZVxuICAgICAgKX1cbiAgICAgIHN0eWxlPXt7IC4uLkNBUkRfU1RZTEUsIC4uLnN0eWxlIH19XG4gICAgICB7Li4ucHJvcHN9XG4gICAgLz5cbiAgKVxufVxuXG5leHBvcnQgZnVuY3Rpb24gQ2FyZEhlYWRlcih7XG4gIGNsYXNzTmFtZSxcbiAgLi4ucHJvcHNcbn06IFJlYWN0LkhUTUxBdHRyaWJ1dGVzPEhUTUxEaXZFbGVtZW50Pikge1xuICByZXR1cm4gKFxuICAgIDxkaXZcbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICdmbGV4IGZsZXgtY29sIGdhcC0xLjUgcC00IGJvcmRlci1iIGJvcmRlci1taWRncm91bmQvMTUnLFxuICAgICAgICBjbGFzc05hbWVcbiAgICAgICl9XG4gICAgICB7Li4ucHJvcHN9XG4gICAgLz5cbiAgKVxufVxuXG5leHBvcnQgZnVuY3Rpb24gQ2FyZFRpdGxlKHtcbiAgY2xhc3NOYW1lLFxuICAuLi5wcm9wc1xufTogUmVhY3QuSFRNTEF0dHJpYnV0ZXM8SFRNTEhlYWRpbmdFbGVtZW50Pikge1xuICByZXR1cm4gKFxuICAgIDxoM1xuICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgJ2ZvbnQtZXhwYW5kZWQgdGV4dC1zbSBmb250LWJvbGQgdHJhY2tpbmctWzAuMDhlbV0gdXBwZXJjYXNlJyxcbiAgICAgICAgY2xhc3NOYW1lXG4gICAgICApfVxuICAgICAgey4uLnByb3BzfVxuICAgIC8+XG4gIClcbn1cblxuZXhwb3J0IGZ1bmN0aW9uIENhcmREZXNjcmlwdGlvbih7XG4gIGNsYXNzTmFtZSxcbiAgLi4ucHJvcHNcbn06IFJlYWN0LkhUTUxBdHRyaWJ1dGVzPEhUTUxQYXJhZ3JhcGhFbGVtZW50Pikge1xuICByZXR1cm4gKFxuICAgIDxwXG4gICAgICBjbGFzc05hbWU9e2NuKCdmb250LW1vbmR3ZXN0IHRleHQteHMgdGV4dC1taWRncm91bmQvNjAnLCBjbGFzc05hbWUpfVxuICAgICAgey4uLnByb3BzfVxuICAgIC8+XG4gIClcbn1cblxuZXhwb3J0IGZ1bmN0aW9uIENhcmRDb250ZW50KHtcbiAgY2xhc3NOYW1lLFxuICAuLi5wcm9wc1xufTogUmVhY3QuSFRNTEF0dHJpYnV0ZXM8SFRNTERpdkVsZW1lbnQ+KSB7XG4gIHJldHVybiA8ZGl2IGNsYXNzTmFtZT17Y24oJ3AtNCcsIGNsYXNzTmFtZSl9IHsuLi5wcm9wc30gLz5cbn1cbiJdLAogICJtYXBwaW5ncyI6ICJBQTBCSTtBQTFCSixTQUFTLFVBQVU7QUFhbkIsTUFBTSxhQUFrQztBQUFBLEVBQ3RDLFlBQVk7QUFBQSxFQUNaLGFBQWE7QUFBQSxFQUNiLFdBQVc7QUFBQSxFQUNYLFVBQVU7QUFDWjtBQUVPLGdCQUFTLEtBQUs7QUFBQSxFQUNuQjtBQUFBLEVBQ0E7QUFBQSxFQUNBLEdBQUc7QUFDTCxHQUF5QztBQUN2QyxTQUNFO0FBQUEsSUFBQztBQUFBO0FBQUEsTUFDQyxXQUFXO0FBQUEsUUFDVDtBQUFBLFFBQ0E7QUFBQSxNQUNGO0FBQUEsTUFDQSxPQUFPLEVBQUUsR0FBRyxZQUFZLEdBQUcsTUFBTTtBQUFBLE1BQ2hDLEdBQUc7QUFBQTtBQUFBLEVBQ047QUFFSjtBQUVPLGdCQUFTLFdBQVc7QUFBQSxFQUN6QjtBQUFBLEVBQ0EsR0FBRztBQUNMLEdBQXlDO0FBQ3ZDLFNBQ0U7QUFBQSxJQUFDO0FBQUE7QUFBQSxNQUNDLFdBQVc7QUFBQSxRQUNUO0FBQUEsUUFDQTtBQUFBLE1BQ0Y7QUFBQSxNQUNDLEdBQUc7QUFBQTtBQUFBLEVBQ047QUFFSjtBQUVPLGdCQUFTLFVBQVU7QUFBQSxFQUN4QjtBQUFBLEVBQ0EsR0FBRztBQUNMLEdBQTZDO0FBQzNDLFNBQ0U7QUFBQSxJQUFDO0FBQUE7QUFBQSxNQUNDLFdBQVc7QUFBQSxRQUNUO0FBQUEsUUFDQTtBQUFBLE1BQ0Y7QUFBQSxNQUNDLEdBQUc7QUFBQTtBQUFBLEVBQ047QUFFSjtBQUVPLGdCQUFTLGdCQUFnQjtBQUFBLEVBQzlCO0FBQUEsRUFDQSxHQUFHO0FBQ0wsR0FBK0M7QUFDN0MsU0FDRTtBQUFBLElBQUM7QUFBQTtBQUFBLE1BQ0MsV0FBVyxHQUFHLDJDQUEyQyxTQUFTO0FBQUEsTUFDakUsR0FBRztBQUFBO0FBQUEsRUFDTjtBQUVKO0FBRU8sZ0JBQVMsWUFBWTtBQUFBLEVBQzFCO0FBQUEsRUFDQSxHQUFHO0FBQ0wsR0FBeUM7QUFDdkMsU0FBTyxvQkFBQyxTQUFJLFdBQVcsR0FBRyxPQUFPLFNBQVMsR0FBSSxHQUFHLE9BQU87QUFDMUQ7IiwKICAibmFtZXMiOiBbXQp9Cg==
