import { jsx, jsxs } from "react/jsx-runtime";
import { cn } from "../../../utils/index.js";
import { Small } from "./small.js";
export function Legend({
  children,
  className,
  label,
  sub,
  ...props
}) {
  return /* @__PURE__ */ jsxs("hgroup", { className: cn("flex flex-col gap-2", className), ...props, children: [
    /* @__PURE__ */ jsx(Small, { children: label }),
    sub && /* @__PURE__ */ jsxs(Small, { className: "opacity-50", children: [
      "- ",
      sub
    ] }),
    children
  ] });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi8uLi91dGlscydcblxuaW1wb3J0IHsgU21hbGwgfSBmcm9tICcuL3NtYWxsJ1xuXG5leHBvcnQgZnVuY3Rpb24gTGVnZW5kKHtcbiAgY2hpbGRyZW4sXG4gIGNsYXNzTmFtZSxcbiAgbGFiZWwsXG4gIHN1YixcbiAgLi4ucHJvcHNcbn06IExlZ2VuZFByb3BzKSB7XG4gIHJldHVybiAoXG4gICAgPGhncm91cCBjbGFzc05hbWU9e2NuKCdmbGV4IGZsZXgtY29sIGdhcC0yJywgY2xhc3NOYW1lKX0gey4uLnByb3BzfT5cbiAgICAgIDxTbWFsbD57bGFiZWx9PC9TbWFsbD5cbiAgICAgIHtzdWIgJiYgPFNtYWxsIGNsYXNzTmFtZT1cIm9wYWNpdHktNTBcIj4tIHtzdWJ9PC9TbWFsbD59XG4gICAgICB7Y2hpbGRyZW59XG4gICAgPC9oZ3JvdXA+XG4gIClcbn1cblxuaW50ZXJmYWNlIExlZ2VuZFByb3BzIGV4dGVuZHMgUmVhY3QuQ29tcG9uZW50UHJvcHM8J2hncm91cCc+IHtcbiAgbGFiZWw6IFJlYWN0LlJlYWN0Tm9kZVxuICBzdWI/OiBSZWFjdC5SZWFjdE5vZGVcbn1cbiJdLAogICJtYXBwaW5ncyI6ICJBQWFNLGNBQ1EsWUFEUjtBQWJOLFNBQVMsVUFBVTtBQUVuQixTQUFTLGFBQWE7QUFFZixnQkFBUyxPQUFPO0FBQUEsRUFDckI7QUFBQSxFQUNBO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFBQSxFQUNBLEdBQUc7QUFDTCxHQUFnQjtBQUNkLFNBQ0UscUJBQUMsWUFBTyxXQUFXLEdBQUcsdUJBQXVCLFNBQVMsR0FBSSxHQUFHLE9BQzNEO0FBQUEsd0JBQUMsU0FBTyxpQkFBTTtBQUFBLElBQ2IsT0FBTyxxQkFBQyxTQUFNLFdBQVUsY0FBYTtBQUFBO0FBQUEsTUFBRztBQUFBLE9BQUk7QUFBQSxJQUM1QztBQUFBLEtBQ0g7QUFFSjsiLAogICJuYW1lcyI6IFtdCn0K
