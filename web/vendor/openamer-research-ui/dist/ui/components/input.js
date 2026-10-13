import { jsx } from "react/jsx-runtime";
import { cn } from "../../utils/index.js";
export function Input({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    "input",
    {
      className: cn(
        "flex h-9 w-full border border-midground/15 bg-background/40 px-3 py-1 font-courier text-sm transition-colors",
        "placeholder:text-midground/50",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/30 focus-visible:border-midground/25",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className
      ),
      ...props
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuZXhwb3J0IGZ1bmN0aW9uIElucHV0KHtcbiAgY2xhc3NOYW1lLFxuICAuLi5wcm9wc1xufTogUmVhY3QuSW5wdXRIVE1MQXR0cmlidXRlczxIVE1MSW5wdXRFbGVtZW50Pikge1xuICByZXR1cm4gKFxuICAgIDxpbnB1dFxuICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgJ2ZsZXggaC05IHctZnVsbCBib3JkZXIgYm9yZGVyLW1pZGdyb3VuZC8xNSBiZy1iYWNrZ3JvdW5kLzQwIHB4LTMgcHktMSBmb250LWNvdXJpZXIgdGV4dC1zbSB0cmFuc2l0aW9uLWNvbG9ycycsXG4gICAgICAgICdwbGFjZWhvbGRlcjp0ZXh0LW1pZGdyb3VuZC81MCcsXG4gICAgICAgICdmb2N1cy12aXNpYmxlOm91dGxpbmUtbm9uZSBmb2N1cy12aXNpYmxlOnJpbmctMSBmb2N1cy12aXNpYmxlOnJpbmctbWlkZ3JvdW5kLzMwIGZvY3VzLXZpc2libGU6Ym9yZGVyLW1pZGdyb3VuZC8yNScsXG4gICAgICAgICdkaXNhYmxlZDpjdXJzb3Itbm90LWFsbG93ZWQgZGlzYWJsZWQ6b3BhY2l0eS01MCcsXG4gICAgICAgIGNsYXNzTmFtZVxuICAgICAgKX1cbiAgICAgIHsuLi5wcm9wc31cbiAgICAvPlxuICApXG59XG5cbiJdLAogICJtYXBwaW5ncyI6ICJBQU9JO0FBUEosU0FBUyxVQUFVO0FBRVosZ0JBQVMsTUFBTTtBQUFBLEVBQ3BCO0FBQUEsRUFDQSxHQUFHO0FBQ0wsR0FBZ0Q7QUFDOUMsU0FDRTtBQUFBLElBQUM7QUFBQTtBQUFBLE1BQ0MsV0FBVztBQUFBLFFBQ1Q7QUFBQSxRQUNBO0FBQUEsUUFDQTtBQUFBLFFBQ0E7QUFBQSxRQUNBO0FBQUEsTUFDRjtBQUFBLE1BQ0MsR0FBRztBQUFBO0FBQUEsRUFDTjtBQUVKOyIsCiAgIm5hbWVzIjogW10KfQo=
