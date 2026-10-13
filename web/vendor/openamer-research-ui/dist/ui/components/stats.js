import { jsx, jsxs } from "react/jsx-runtime";
import { cn } from "../../utils/index.js";
import { Typography } from "./typography/index.js";
export function Stats({ className, items, flip, ...props }) {
  return /* @__PURE__ */ jsx("div", { className: cn("flex w-full flex-col gap-5", className), ...props, children: items.map(({ label, value }) => {
    const valueText = /* @__PURE__ */ jsx(
      Typography,
      {
        className: "text-xs leading-[1.4] tracking-widest",
        expanded: true,
        children: typeof value === "string" ? value : value.node
      }
    );
    const labelText = /* @__PURE__ */ jsx(Typography, { className: "leading-none tracking-[0.2em] opacity-60", mono: true, children: typeof label === "string" ? label : label.node });
    return /* @__PURE__ */ jsxs(
      "div",
      {
        className: "text-midground text-display grid grid-cols-[auto_1fr_auto] items-center gap-2.5",
        children: [
          flip ? labelText : valueText,
          /* @__PURE__ */ jsx(
            Typography,
            {
              className: "min-w-0 overflow-hidden text-[13px] leading-[1.4] tracking-[0.4em] opacity-20",
              expanded: true,
              children: "\xB7".repeat(100)
            }
          ),
          flip ? valueText : labelText
        ]
      },
      (typeof label === "string" ? label : label.key) + "@@@" + (typeof value === "string" ? value : value.key)
    );
  }) });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IFJlYWN0LCB7IFJlYWN0Tm9kZSB9IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyBjbiB9IGZyb20gJy4uLy4uL3V0aWxzJ1xuXG5pbXBvcnQgeyBUeXBvZ3JhcGh5IH0gZnJvbSAnLi90eXBvZ3JhcGh5J1xuXG5leHBvcnQgZnVuY3Rpb24gU3RhdHMoeyBjbGFzc05hbWUsIGl0ZW1zLCBmbGlwLCAuLi5wcm9wcyB9OiBTdGF0c1Byb3BzKSB7XG4gIHJldHVybiAoXG4gICAgPGRpdiBjbGFzc05hbWU9e2NuKCdmbGV4IHctZnVsbCBmbGV4LWNvbCBnYXAtNScsIGNsYXNzTmFtZSl9IHsuLi5wcm9wc30+XG4gICAgICB7aXRlbXMubWFwKCh7IGxhYmVsLCB2YWx1ZSB9KSA9PiB7XG4gICAgICAgIGNvbnN0IHZhbHVlVGV4dCA9IChcbiAgICAgICAgICA8VHlwb2dyYXBoeVxuICAgICAgICAgICAgY2xhc3NOYW1lPVwidGV4dC14cyBsZWFkaW5nLVsxLjRdIHRyYWNraW5nLXdpZGVzdFwiXG4gICAgICAgICAgICBleHBhbmRlZFxuICAgICAgICAgID5cbiAgICAgICAgICAgIHt0eXBlb2YgdmFsdWUgPT09ICdzdHJpbmcnID8gdmFsdWUgOiB2YWx1ZS5ub2RlfVxuICAgICAgICAgIDwvVHlwb2dyYXBoeT5cbiAgICAgICAgKVxuICAgICAgICBjb25zdCBsYWJlbFRleHQgPSAoXG4gICAgICAgICAgPFR5cG9ncmFwaHkgY2xhc3NOYW1lPVwibGVhZGluZy1ub25lIHRyYWNraW5nLVswLjJlbV0gb3BhY2l0eS02MFwiIG1vbm8+XG4gICAgICAgICAgICB7dHlwZW9mIGxhYmVsID09PSAnc3RyaW5nJyA/IGxhYmVsIDogbGFiZWwubm9kZX1cbiAgICAgICAgICA8L1R5cG9ncmFwaHk+XG4gICAgICAgIClcblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxkaXZcbiAgICAgICAgICAgIGNsYXNzTmFtZT1cInRleHQtbWlkZ3JvdW5kIHRleHQtZGlzcGxheSBncmlkIGdyaWQtY29scy1bYXV0b18xZnJfYXV0b10gaXRlbXMtY2VudGVyIGdhcC0yLjVcIlxuICAgICAgICAgICAga2V5PXsodHlwZW9mIGxhYmVsID09PSAnc3RyaW5nJyA/IGxhYmVsIDogbGFiZWwua2V5ICkgKyAnQEBAJysodHlwZW9mIHZhbHVlID09PSAnc3RyaW5nJyA/IHZhbHVlIDogdmFsdWUua2V5KX1cbiAgICAgICAgICA+XG4gICAgICAgICAgICB7ZmxpcCA/IGxhYmVsVGV4dCA6IHZhbHVlVGV4dH1cblxuICAgICAgICAgICAgPFR5cG9ncmFwaHlcbiAgICAgICAgICAgICAgY2xhc3NOYW1lPVwibWluLXctMCBvdmVyZmxvdy1oaWRkZW4gdGV4dC1bMTNweF0gbGVhZGluZy1bMS40XSB0cmFja2luZy1bMC40ZW1dIG9wYWNpdHktMjBcIlxuICAgICAgICAgICAgICBleHBhbmRlZFxuICAgICAgICAgICAgPlxuICAgICAgICAgICAgICB7J1x1MDBCNycucmVwZWF0KDEwMCl9XG4gICAgICAgICAgICA8L1R5cG9ncmFwaHk+XG5cbiAgICAgICAgICAgIHtmbGlwID8gdmFsdWVUZXh0IDogbGFiZWxUZXh0fVxuICAgICAgICAgIDwvZGl2PlxuICAgICAgICApXG4gICAgICB9KX1cbiAgICA8L2Rpdj5cbiAgKVxufVxuXG5pbnRlcmZhY2UgU3RhdHNQcm9wcyBleHRlbmRzIFJlYWN0LkNvbXBvbmVudFByb3BzPCdkaXYnPiB7XG4gIGl0ZW1zOiB7XG4gICAgbGFiZWw6IHN0cmluZyB8IHtrZXk6IHN0cmluZywgbm9kZTogUmVhY3ROb2RlfVxuICAgIHZhbHVlOiBzdHJpbmcgfCB7a2V5OiBzdHJpbmcsIG5vZGU6IFJlYWN0Tm9kZX1cbiAgfVtdXG4gIGZsaXA/OiBib29sZWFuXG59XG4iXSwKICAibWFwcGluZ3MiOiAiQUFXVSxjQWNBLFlBZEE7QUFUVixTQUFTLFVBQVU7QUFFbkIsU0FBUyxrQkFBa0I7QUFFcEIsZ0JBQVMsTUFBTSxFQUFFLFdBQVcsT0FBTyxNQUFNLEdBQUcsTUFBTSxHQUFlO0FBQ3RFLFNBQ0Usb0JBQUMsU0FBSSxXQUFXLEdBQUcsOEJBQThCLFNBQVMsR0FBSSxHQUFHLE9BQzlELGdCQUFNLElBQUksQ0FBQyxFQUFFLE9BQU8sTUFBTSxNQUFNO0FBQy9CLFVBQU0sWUFDSjtBQUFBLE1BQUM7QUFBQTtBQUFBLFFBQ0MsV0FBVTtBQUFBLFFBQ1YsVUFBUTtBQUFBLFFBRVAsaUJBQU8sVUFBVSxXQUFXLFFBQVEsTUFBTTtBQUFBO0FBQUEsSUFDN0M7QUFFRixVQUFNLFlBQ0osb0JBQUMsY0FBVyxXQUFVLDRDQUEyQyxNQUFJLE1BQ2xFLGlCQUFPLFVBQVUsV0FBVyxRQUFRLE1BQU0sTUFDN0M7QUFHRixXQUNFO0FBQUEsTUFBQztBQUFBO0FBQUEsUUFDQyxXQUFVO0FBQUEsUUFHVDtBQUFBLGlCQUFPLFlBQVk7QUFBQSxVQUVwQjtBQUFBLFlBQUM7QUFBQTtBQUFBLGNBQ0MsV0FBVTtBQUFBLGNBQ1YsVUFBUTtBQUFBLGNBRVAsaUJBQUksT0FBTyxHQUFHO0FBQUE7QUFBQSxVQUNqQjtBQUFBLFVBRUMsT0FBTyxZQUFZO0FBQUE7QUFBQTtBQUFBLE9BWGQsT0FBTyxVQUFVLFdBQVcsUUFBUSxNQUFNLE9BQVEsU0FBTyxPQUFPLFVBQVUsV0FBVyxRQUFRLE1BQU07QUFBQSxJQVkzRztBQUFBLEVBRUosQ0FBQyxHQUNIO0FBRUo7IiwKICAibmFtZXMiOiBbXQp9Cg==
