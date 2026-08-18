import { jsx, jsxs } from "react/jsx-runtime";
import { cn } from "../../../utils/index.js";
export function ChevronIcon({
  className,
  direction = "left",
  ...props
}) {
  return /* @__PURE__ */ jsxs(
    "svg",
    {
      className: cn(
        direction === "left" && "rotate-90",
        direction === "right" && "-rotate-90",
        className
      ),
      fill: "none",
      viewBox: "0 0 8 13",
      ...props,
      children: [
        /* @__PURE__ */ jsx(
          "path",
          {
            clipRule: "evenodd",
            d: "M0 7.49765h5V4.9969H1e-7z",
            fill: "currentColor",
            fillRule: "evenodd"
          }
        ),
        /* @__PURE__ */ jsx(
          "path",
          {
            clipRule: "evenodd",
            d: "M2.5 2.49765v7.5h2.50075v-7.5z",
            fill: "currentColor",
            fillRule: "evenodd"
          }
        ),
        /* @__PURE__ */ jsx(
          "path",
          {
            clipRule: "evenodd",
            d: "M5 .0000031V2.4996h2.4996V.0000032zM5 9.99805v2.49965h2.4996V9.99805z",
            fill: "currentColor",
            fillRule: "evenodd"
          }
        )
      ]
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHR5cGUgeyBTVkdQcm9wcyB9IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyBjbiB9IGZyb20gJy4uLy4uLy4uL3V0aWxzJ1xuXG5leHBvcnQgZnVuY3Rpb24gQ2hldnJvbkljb24oe1xuICBjbGFzc05hbWUsXG4gIGRpcmVjdGlvbiA9ICdsZWZ0JyxcbiAgLi4ucHJvcHNcbn06IENoZXZyb25JY29uUHJvcHMpIHtcbiAgcmV0dXJuIChcbiAgICA8c3ZnXG4gICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICBkaXJlY3Rpb24gPT09ICdsZWZ0JyAmJiAncm90YXRlLTkwJyxcbiAgICAgICAgZGlyZWN0aW9uID09PSAncmlnaHQnICYmICctcm90YXRlLTkwJyxcbiAgICAgICAgY2xhc3NOYW1lXG4gICAgICApfVxuICAgICAgZmlsbD1cIm5vbmVcIlxuICAgICAgdmlld0JveD1cIjAgMCA4IDEzXCJcbiAgICAgIHsuLi5wcm9wc31cbiAgICA+XG4gICAgICA8cGF0aFxuICAgICAgICBjbGlwUnVsZT1cImV2ZW5vZGRcIlxuICAgICAgICBkPVwiTTAgNy40OTc2NWg1VjQuOTk2OUgxZS03elwiXG4gICAgICAgIGZpbGw9XCJjdXJyZW50Q29sb3JcIlxuICAgICAgICBmaWxsUnVsZT1cImV2ZW5vZGRcIlxuICAgICAgLz5cbiAgICAgIDxwYXRoXG4gICAgICAgIGNsaXBSdWxlPVwiZXZlbm9kZFwiXG4gICAgICAgIGQ9XCJNMi41IDIuNDk3NjV2Ny41aDIuNTAwNzV2LTcuNXpcIlxuICAgICAgICBmaWxsPVwiY3VycmVudENvbG9yXCJcbiAgICAgICAgZmlsbFJ1bGU9XCJldmVub2RkXCJcbiAgICAgIC8+XG4gICAgICA8cGF0aFxuICAgICAgICBjbGlwUnVsZT1cImV2ZW5vZGRcIlxuICAgICAgICBkPVwiTTUgLjAwMDAwMzFWMi40OTk2aDIuNDk5NlYuMDAwMDAzMnpNNSA5Ljk5ODA1djIuNDk5NjVoMi40OTk2VjkuOTk4MDV6XCJcbiAgICAgICAgZmlsbD1cImN1cnJlbnRDb2xvclwiXG4gICAgICAgIGZpbGxSdWxlPVwiZXZlbm9kZFwiXG4gICAgICAvPlxuICAgIDwvc3ZnPlxuICApXG59XG5cbmludGVyZmFjZSBDaGV2cm9uSWNvblByb3BzIGV4dGVuZHMgU1ZHUHJvcHM8U1ZHU1ZHRWxlbWVudD4ge1xuICBkaXJlY3Rpb24/OiAnbGVmdCcgfCAncmlnaHQnXG59XG4iXSwKICAibWFwcGluZ3MiOiAiQUFVSSxTQVVFLEtBVkY7QUFSSixTQUFTLFVBQVU7QUFFWixnQkFBUyxZQUFZO0FBQUEsRUFDMUI7QUFBQSxFQUNBLFlBQVk7QUFBQSxFQUNaLEdBQUc7QUFDTCxHQUFxQjtBQUNuQixTQUNFO0FBQUEsSUFBQztBQUFBO0FBQUEsTUFDQyxXQUFXO0FBQUEsUUFDVCxjQUFjLFVBQVU7QUFBQSxRQUN4QixjQUFjLFdBQVc7QUFBQSxRQUN6QjtBQUFBLE1BQ0Y7QUFBQSxNQUNBLE1BQUs7QUFBQSxNQUNMLFNBQVE7QUFBQSxNQUNQLEdBQUc7QUFBQSxNQUVKO0FBQUE7QUFBQSxVQUFDO0FBQUE7QUFBQSxZQUNDLFVBQVM7QUFBQSxZQUNULEdBQUU7QUFBQSxZQUNGLE1BQUs7QUFBQSxZQUNMLFVBQVM7QUFBQTtBQUFBLFFBQ1g7QUFBQSxRQUNBO0FBQUEsVUFBQztBQUFBO0FBQUEsWUFDQyxVQUFTO0FBQUEsWUFDVCxHQUFFO0FBQUEsWUFDRixNQUFLO0FBQUEsWUFDTCxVQUFTO0FBQUE7QUFBQSxRQUNYO0FBQUEsUUFDQTtBQUFBLFVBQUM7QUFBQTtBQUFBLFlBQ0MsVUFBUztBQUFBLFlBQ1QsR0FBRTtBQUFBLFlBQ0YsTUFBSztBQUFBLFlBQ0wsVUFBUztBQUFBO0FBQUEsUUFDWDtBQUFBO0FBQUE7QUFBQSxFQUNGO0FBRUo7IiwKICAibmFtZXMiOiBbXQp9Cg==
