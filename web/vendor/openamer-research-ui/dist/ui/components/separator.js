import { jsx } from "react/jsx-runtime";
import { cn } from "../../utils/index.js";
export function Separator({
  className,
  orientation = "horizontal",
  ...props
}) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "aria-orientation": orientation,
      role: "separator",
      className: cn(
        "shrink-0 bg-midground/15",
        orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
        className
      ),
      ...props
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuZXhwb3J0IGZ1bmN0aW9uIFNlcGFyYXRvcih7XG4gIGNsYXNzTmFtZSxcbiAgb3JpZW50YXRpb24gPSAnaG9yaXpvbnRhbCcsXG4gIC4uLnByb3BzXG59OiBTZXBhcmF0b3JQcm9wcykge1xuICByZXR1cm4gKFxuICAgIDxkaXZcbiAgICAgIGFyaWEtb3JpZW50YXRpb249e29yaWVudGF0aW9ufVxuICAgICAgcm9sZT1cInNlcGFyYXRvclwiXG4gICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAnc2hyaW5rLTAgYmctbWlkZ3JvdW5kLzE1JyxcbiAgICAgICAgb3JpZW50YXRpb24gPT09ICdob3Jpem9udGFsJyA/ICdoLXB4IHctZnVsbCcgOiAnaC1mdWxsIHctcHgnLFxuICAgICAgICBjbGFzc05hbWVcbiAgICAgICl9XG4gICAgICB7Li4ucHJvcHN9XG4gICAgLz5cbiAgKVxufVxuXG5pbnRlcmZhY2UgU2VwYXJhdG9yUHJvcHMgZXh0ZW5kcyBSZWFjdC5IVE1MQXR0cmlidXRlczxIVE1MRGl2RWxlbWVudD4ge1xuICBvcmllbnRhdGlvbj86ICdob3Jpem9udGFsJyB8ICd2ZXJ0aWNhbCdcbn1cbiJdLAogICJtYXBwaW5ncyI6ICJBQVFJO0FBUkosU0FBUyxVQUFVO0FBRVosZ0JBQVMsVUFBVTtBQUFBLEVBQ3hCO0FBQUEsRUFDQSxjQUFjO0FBQUEsRUFDZCxHQUFHO0FBQ0wsR0FBbUI7QUFDakIsU0FDRTtBQUFBLElBQUM7QUFBQTtBQUFBLE1BQ0Msb0JBQWtCO0FBQUEsTUFDbEIsTUFBSztBQUFBLE1BQ0wsV0FBVztBQUFBLFFBQ1Q7QUFBQSxRQUNBLGdCQUFnQixlQUFlLGdCQUFnQjtBQUFBLFFBQy9DO0FBQUEsTUFDRjtBQUFBLE1BQ0MsR0FBRztBQUFBO0FBQUEsRUFDTjtBQUVKOyIsCiAgIm5hbWVzIjogW10KfQo=
