import { jsx } from "react/jsx-runtime";
import { forwardRef } from "react";
import { cn } from "../../../utils/index.js";
import { Typography } from "./index.js";
export const H2 = forwardRef(
  ({ className, ...props }, ref) => {
    return /* @__PURE__ */ jsx(
      Typography,
      {
        as: "h2",
        className: cn("font-bold", className),
        variant: "lg",
        ...{ ref, ...props }
      }
    );
  }
);
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgZm9yd2FyZFJlZiB9IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyBjbiB9IGZyb20gJy4uLy4uLy4uL3V0aWxzJ1xuXG5pbXBvcnQgeyBUeXBvZ3JhcGh5LCB0eXBlIFR5cG9ncmFwaHlQcm9wcyB9IGZyb20gJy4nXG5cbmV4cG9ydCBjb25zdCBIMiA9IGZvcndhcmRSZWY8SFRNTEhlYWRpbmdFbGVtZW50LCBUeXBvZ3JhcGh5UHJvcHM8J2gyJz4+KFxuICAoeyBjbGFzc05hbWUsIC4uLnByb3BzIH0sIHJlZikgPT4ge1xuICAgIHJldHVybiAoXG4gICAgICA8VHlwb2dyYXBoeVxuICAgICAgICBhcz1cImgyXCJcbiAgICAgICAgY2xhc3NOYW1lPXtjbignZm9udC1ib2xkJywgY2xhc3NOYW1lKX1cbiAgICAgICAgdmFyaWFudD1cImxnXCJcbiAgICAgICAgey4uLnsgcmVmLCAuLi5wcm9wcyB9fVxuICAgICAgLz5cbiAgICApXG4gIH1cbilcbiJdLAogICJtYXBwaW5ncyI6ICJBQVNNO0FBVE4sU0FBUyxrQkFBa0I7QUFFM0IsU0FBUyxVQUFVO0FBRW5CLFNBQVMsa0JBQXdDO0FBRTFDLGFBQU0sS0FBSztBQUFBLEVBQ2hCLENBQUMsRUFBRSxXQUFXLEdBQUcsTUFBTSxHQUFHLFFBQVE7QUFDaEMsV0FDRTtBQUFBLE1BQUM7QUFBQTtBQUFBLFFBQ0MsSUFBRztBQUFBLFFBQ0gsV0FBVyxHQUFHLGFBQWEsU0FBUztBQUFBLFFBQ3BDLFNBQVE7QUFBQSxRQUNQLEdBQUcsRUFBRSxLQUFLLEdBQUcsTUFBTTtBQUFBO0FBQUEsSUFDdEI7QUFBQSxFQUVKO0FBQ0Y7IiwKICAibmFtZXMiOiBbXQp9Cg==
