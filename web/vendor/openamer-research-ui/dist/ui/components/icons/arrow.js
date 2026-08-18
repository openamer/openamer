import { jsx, jsxs } from "react/jsx-runtime";
import { cn } from "../../../utils/index.js";
export function ArrowIcon({
  className,
  direction = "down",
  ...props
}) {
  return /* @__PURE__ */ jsxs(
    "svg",
    {
      className: cn(
        direction === "up" && "rotate-180",
        direction === "left" && "rotate-90",
        direction === "right" && "-rotate-90",
        "origin-center",
        className
      ),
      fill: "none",
      viewBox: "0 0 13 15",
      ...props,
      children: [
        /* @__PURE__ */ jsx(
          "path",
          {
            clipRule: "evenodd",
            d: "M5 15V0h2.50075v15z",
            fill: "currentColor",
            fillRule: "evenodd"
          }
        ),
        /* @__PURE__ */ jsx(
          "path",
          {
            clipRule: "evenodd",
            d: "M10 12.5007H2.5V9.99998H10zM12.4976 9.99951H9.99805v-2.4996h2.49955zM2.4996 9.99951H0v-2.4996h2.4996z",
            fill: "currentColor",
            fillRule: "evenodd"
          }
        )
      ]
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHR5cGUgeyBTVkdQcm9wcyB9IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyBjbiB9IGZyb20gJy4uLy4uLy4uL3V0aWxzJ1xuXG5leHBvcnQgZnVuY3Rpb24gQXJyb3dJY29uKHtcbiAgY2xhc3NOYW1lLFxuICBkaXJlY3Rpb24gPSAnZG93bicsXG4gIC4uLnByb3BzXG59OiBBcnJvd0ljb25Qcm9wcykge1xuICByZXR1cm4gKFxuICAgIDxzdmdcbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgIGRpcmVjdGlvbiA9PT0gJ3VwJyAmJiAncm90YXRlLTE4MCcsXG4gICAgICAgIGRpcmVjdGlvbiA9PT0gJ2xlZnQnICYmICdyb3RhdGUtOTAnLFxuICAgICAgICBkaXJlY3Rpb24gPT09ICdyaWdodCcgJiYgJy1yb3RhdGUtOTAnLFxuICAgICAgICAnb3JpZ2luLWNlbnRlcicsXG4gICAgICAgIGNsYXNzTmFtZVxuICAgICAgKX1cbiAgICAgIGZpbGw9XCJub25lXCJcbiAgICAgIHZpZXdCb3g9XCIwIDAgMTMgMTVcIlxuICAgICAgey4uLnByb3BzfVxuICAgID5cbiAgICAgIDxwYXRoXG4gICAgICAgIGNsaXBSdWxlPVwiZXZlbm9kZFwiXG4gICAgICAgIGQ9XCJNNSAxNVYwaDIuNTAwNzV2MTV6XCJcbiAgICAgICAgZmlsbD1cImN1cnJlbnRDb2xvclwiXG4gICAgICAgIGZpbGxSdWxlPVwiZXZlbm9kZFwiXG4gICAgICAvPlxuXG4gICAgICA8cGF0aFxuICAgICAgICBjbGlwUnVsZT1cImV2ZW5vZGRcIlxuICAgICAgICBkPVwiTTEwIDEyLjUwMDdIMi41VjkuOTk5OThIMTB6TTEyLjQ5NzYgOS45OTk1MUg5Ljk5ODA1di0yLjQ5OTZoMi40OTk1NXpNMi40OTk2IDkuOTk5NTFIMHYtMi40OTk2aDIuNDk5NnpcIlxuICAgICAgICBmaWxsPVwiY3VycmVudENvbG9yXCJcbiAgICAgICAgZmlsbFJ1bGU9XCJldmVub2RkXCJcbiAgICAgIC8+XG4gICAgPC9zdmc+XG4gIClcbn1cblxuaW50ZXJmYWNlIEFycm93SWNvblByb3BzIGV4dGVuZHMgU1ZHUHJvcHM8U1ZHU1ZHRWxlbWVudD4ge1xuICBkaXJlY3Rpb24/OiAnZG93bicgfCAnbGVmdCcgfCAncmlnaHQnIHwgJ3VwJ1xufVxuIl0sCiAgIm1hcHBpbmdzIjogIkFBVUksU0FZRSxLQVpGO0FBUkosU0FBUyxVQUFVO0FBRVosZ0JBQVMsVUFBVTtBQUFBLEVBQ3hCO0FBQUEsRUFDQSxZQUFZO0FBQUEsRUFDWixHQUFHO0FBQ0wsR0FBbUI7QUFDakIsU0FDRTtBQUFBLElBQUM7QUFBQTtBQUFBLE1BQ0MsV0FBVztBQUFBLFFBQ1QsY0FBYyxRQUFRO0FBQUEsUUFDdEIsY0FBYyxVQUFVO0FBQUEsUUFDeEIsY0FBYyxXQUFXO0FBQUEsUUFDekI7QUFBQSxRQUNBO0FBQUEsTUFDRjtBQUFBLE1BQ0EsTUFBSztBQUFBLE1BQ0wsU0FBUTtBQUFBLE1BQ1AsR0FBRztBQUFBLE1BRUo7QUFBQTtBQUFBLFVBQUM7QUFBQTtBQUFBLFlBQ0MsVUFBUztBQUFBLFlBQ1QsR0FBRTtBQUFBLFlBQ0YsTUFBSztBQUFBLFlBQ0wsVUFBUztBQUFBO0FBQUEsUUFDWDtBQUFBLFFBRUE7QUFBQSxVQUFDO0FBQUE7QUFBQSxZQUNDLFVBQVM7QUFBQSxZQUNULEdBQUU7QUFBQSxZQUNGLE1BQUs7QUFBQSxZQUNMLFVBQVM7QUFBQTtBQUFBLFFBQ1g7QUFBQTtBQUFBO0FBQUEsRUFDRjtBQUVKOyIsCiAgIm5hbWVzIjogW10KfQo=
