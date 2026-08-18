import { jsx, jsxs } from "react/jsx-runtime";
import { cn } from "../../../utils/index.js";
export function HamburgerIcon({
  className,
  open = false,
  ...props
}) {
  return /* @__PURE__ */ jsxs(
    "svg",
    {
      className: cn("size-5", className),
      fill: "none",
      stroke: "currentColor",
      strokeLinecap: "round",
      strokeWidth: 1.5,
      viewBox: "0 0 24 24",
      ...props,
      children: [
        /* @__PURE__ */ jsx(
          "line",
          {
            className: "origin-center transition-transform duration-200 ease-out",
            style: { transform: open ? "rotate(45deg)" : "translateY(-4px)" },
            x1: 4,
            x2: 20,
            y1: 12,
            y2: 12
          }
        ),
        /* @__PURE__ */ jsx(
          "line",
          {
            className: "transition-opacity duration-200 ease-out",
            style: { opacity: open ? 0 : 1 },
            x1: 4,
            x2: 20,
            y1: 12,
            y2: 12
          }
        ),
        /* @__PURE__ */ jsx(
          "line",
          {
            className: "origin-center transition-transform duration-200 ease-out",
            style: { transform: open ? "rotate(-45deg)" : "translateY(4px)" },
            x1: 4,
            x2: 20,
            y1: 12,
            y2: 12
          }
        )
      ]
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHR5cGUgeyBTVkdQcm9wcyB9IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyBjbiB9IGZyb20gJy4uLy4uLy4uL3V0aWxzJ1xuXG5leHBvcnQgZnVuY3Rpb24gSGFtYnVyZ2VySWNvbih7XG4gIGNsYXNzTmFtZSxcbiAgb3BlbiA9IGZhbHNlLFxuICAuLi5wcm9wc1xufTogSGFtYnVyZ2VySWNvblByb3BzKSB7XG4gIHJldHVybiAoXG4gICAgPHN2Z1xuICAgICAgY2xhc3NOYW1lPXtjbignc2l6ZS01JywgY2xhc3NOYW1lKX1cbiAgICAgIGZpbGw9XCJub25lXCJcbiAgICAgIHN0cm9rZT1cImN1cnJlbnRDb2xvclwiXG4gICAgICBzdHJva2VMaW5lY2FwPVwicm91bmRcIlxuICAgICAgc3Ryb2tlV2lkdGg9ezEuNX1cbiAgICAgIHZpZXdCb3g9XCIwIDAgMjQgMjRcIlxuICAgICAgey4uLnByb3BzfVxuICAgID5cbiAgICAgIDxsaW5lXG4gICAgICAgIGNsYXNzTmFtZT1cIm9yaWdpbi1jZW50ZXIgdHJhbnNpdGlvbi10cmFuc2Zvcm0gZHVyYXRpb24tMjAwIGVhc2Utb3V0XCJcbiAgICAgICAgc3R5bGU9e3sgdHJhbnNmb3JtOiBvcGVuID8gJ3JvdGF0ZSg0NWRlZyknIDogJ3RyYW5zbGF0ZVkoLTRweCknIH19XG4gICAgICAgIHgxPXs0fVxuICAgICAgICB4Mj17MjB9XG4gICAgICAgIHkxPXsxMn1cbiAgICAgICAgeTI9ezEyfVxuICAgICAgLz5cblxuICAgICAgPGxpbmVcbiAgICAgICAgY2xhc3NOYW1lPVwidHJhbnNpdGlvbi1vcGFjaXR5IGR1cmF0aW9uLTIwMCBlYXNlLW91dFwiXG4gICAgICAgIHN0eWxlPXt7IG9wYWNpdHk6IG9wZW4gPyAwIDogMSB9fVxuICAgICAgICB4MT17NH1cbiAgICAgICAgeDI9ezIwfVxuICAgICAgICB5MT17MTJ9XG4gICAgICAgIHkyPXsxMn1cbiAgICAgIC8+XG5cbiAgICAgIDxsaW5lXG4gICAgICAgIGNsYXNzTmFtZT1cIm9yaWdpbi1jZW50ZXIgdHJhbnNpdGlvbi10cmFuc2Zvcm0gZHVyYXRpb24tMjAwIGVhc2Utb3V0XCJcbiAgICAgICAgc3R5bGU9e3sgdHJhbnNmb3JtOiBvcGVuID8gJ3JvdGF0ZSgtNDVkZWcpJyA6ICd0cmFuc2xhdGVZKDRweCknIH19XG4gICAgICAgIHgxPXs0fVxuICAgICAgICB4Mj17MjB9XG4gICAgICAgIHkxPXsxMn1cbiAgICAgICAgeTI9ezEyfVxuICAgICAgLz5cbiAgICA8L3N2Zz5cbiAgKVxufVxuXG5pbnRlcmZhY2UgSGFtYnVyZ2VySWNvblByb3BzIGV4dGVuZHMgU1ZHUHJvcHM8U1ZHU1ZHRWxlbWVudD4ge1xuICBvcGVuPzogYm9vbGVhblxufVxuIl0sCiAgIm1hcHBpbmdzIjogIkFBVUksU0FTRSxLQVRGO0FBUkosU0FBUyxVQUFVO0FBRVosZ0JBQVMsY0FBYztBQUFBLEVBQzVCO0FBQUEsRUFDQSxPQUFPO0FBQUEsRUFDUCxHQUFHO0FBQ0wsR0FBdUI7QUFDckIsU0FDRTtBQUFBLElBQUM7QUFBQTtBQUFBLE1BQ0MsV0FBVyxHQUFHLFVBQVUsU0FBUztBQUFBLE1BQ2pDLE1BQUs7QUFBQSxNQUNMLFFBQU87QUFBQSxNQUNQLGVBQWM7QUFBQSxNQUNkLGFBQWE7QUFBQSxNQUNiLFNBQVE7QUFBQSxNQUNQLEdBQUc7QUFBQSxNQUVKO0FBQUE7QUFBQSxVQUFDO0FBQUE7QUFBQSxZQUNDLFdBQVU7QUFBQSxZQUNWLE9BQU8sRUFBRSxXQUFXLE9BQU8sa0JBQWtCLG1CQUFtQjtBQUFBLFlBQ2hFLElBQUk7QUFBQSxZQUNKLElBQUk7QUFBQSxZQUNKLElBQUk7QUFBQSxZQUNKLElBQUk7QUFBQTtBQUFBLFFBQ047QUFBQSxRQUVBO0FBQUEsVUFBQztBQUFBO0FBQUEsWUFDQyxXQUFVO0FBQUEsWUFDVixPQUFPLEVBQUUsU0FBUyxPQUFPLElBQUksRUFBRTtBQUFBLFlBQy9CLElBQUk7QUFBQSxZQUNKLElBQUk7QUFBQSxZQUNKLElBQUk7QUFBQSxZQUNKLElBQUk7QUFBQTtBQUFBLFFBQ047QUFBQSxRQUVBO0FBQUEsVUFBQztBQUFBO0FBQUEsWUFDQyxXQUFVO0FBQUEsWUFDVixPQUFPLEVBQUUsV0FBVyxPQUFPLG1CQUFtQixrQkFBa0I7QUFBQSxZQUNoRSxJQUFJO0FBQUEsWUFDSixJQUFJO0FBQUEsWUFDSixJQUFJO0FBQUEsWUFDSixJQUFJO0FBQUE7QUFBQSxRQUNOO0FBQUE7QUFBQTtBQUFBLEVBQ0Y7QUFFSjsiLAogICJuYW1lcyI6IFtdCn0K
