import { jsx } from "react/jsx-runtime";
import { cn } from "../../utils/index.js";
export function Socials({ className, items, onNavigate, ...rest }) {
  return /* @__PURE__ */ jsx("div", { className: cn("flex items-center gap-3", className), ...rest, children: items.map(({ external = true, href, icon: Icon, label, onClick }) => /* @__PURE__ */ jsx(
    "a",
    {
      className: "opacity-60 transition-opacity hover:opacity-100",
      href,
      onClick: (e) => {
        onClick?.(e);
        onNavigate?.();
      },
      rel: external ? "noopener noreferrer" : void 0,
      target: external ? "_blank" : void 0,
      title: label,
      children: /* @__PURE__ */ jsx(Icon, {})
    },
    label
  )) });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuZXhwb3J0IGZ1bmN0aW9uIFNvY2lhbHMoeyBjbGFzc05hbWUsIGl0ZW1zLCBvbk5hdmlnYXRlLCAuLi5yZXN0IH06IFNvY2lhbHNQcm9wcykge1xuICByZXR1cm4gKFxuICAgIDxkaXYgY2xhc3NOYW1lPXtjbignZmxleCBpdGVtcy1jZW50ZXIgZ2FwLTMnLCBjbGFzc05hbWUpfSB7Li4ucmVzdH0+XG4gICAgICB7aXRlbXMubWFwKCh7IGV4dGVybmFsID0gdHJ1ZSwgaHJlZiwgaWNvbjogSWNvbiwgbGFiZWwsIG9uQ2xpY2sgfSkgPT4gKFxuICAgICAgICA8YVxuICAgICAgICAgIGNsYXNzTmFtZT1cIm9wYWNpdHktNjAgdHJhbnNpdGlvbi1vcGFjaXR5IGhvdmVyOm9wYWNpdHktMTAwXCJcbiAgICAgICAgICBocmVmPXtocmVmfVxuICAgICAgICAgIGtleT17bGFiZWx9XG4gICAgICAgICAgb25DbGljaz17ZSA9PiB7XG4gICAgICAgICAgICBvbkNsaWNrPy4oZSlcbiAgICAgICAgICAgIG9uTmF2aWdhdGU/LigpXG4gICAgICAgICAgfX1cbiAgICAgICAgICByZWw9e2V4dGVybmFsID8gJ25vb3BlbmVyIG5vcmVmZXJyZXInIDogdW5kZWZpbmVkfVxuICAgICAgICAgIHRhcmdldD17ZXh0ZXJuYWwgPyAnX2JsYW5rJyA6IHVuZGVmaW5lZH1cbiAgICAgICAgICB0aXRsZT17bGFiZWx9XG4gICAgICAgID5cbiAgICAgICAgICA8SWNvbiAvPlxuICAgICAgICA8L2E+XG4gICAgICApKX1cbiAgICA8L2Rpdj5cbiAgKVxufVxuXG5leHBvcnQgaW50ZXJmYWNlIFNvY2lhbExpbmsge1xuICBleHRlcm5hbD86IGJvb2xlYW5cbiAgaHJlZjogc3RyaW5nXG4gIGljb246IFJlYWN0LkNvbXBvbmVudFR5cGU8eyBjbGFzc05hbWU/OiBzdHJpbmcgfT5cbiAgbGFiZWw6IHN0cmluZ1xuICBvbkNsaWNrPzogUmVhY3QuTW91c2VFdmVudEhhbmRsZXJcbn1cblxuaW50ZXJmYWNlIFNvY2lhbHNQcm9wcyBleHRlbmRzIFJlYWN0LkhUTUxBdHRyaWJ1dGVzPEhUTUxEaXZFbGVtZW50PiB7XG4gIGl0ZW1zOiBTb2NpYWxMaW5rW11cbiAgLyoqXG4gICAqIENhbGxlZCAqaW4gYWRkaXRpb24qIHRvIGVhY2ggbGluaydzIGBvbkNsaWNrYCBhZnRlciBhIGNsaWNrIFx1MjAxNCB1c2VmdWwgaW5cbiAgICogbW9iaWxlIGRyYXdlciAvIGRpYWxvZyBjb250ZXh0cyB3aGVyZSBjbGlja2luZyBhIGxpbmsgc2hvdWxkIGFsc28gY2xvc2VcbiAgICogdGhlIHN1cnJvdW5kaW5nIG92ZXJsYXkuXG4gICAqL1xuICBvbk5hdmlnYXRlPzogKCkgPT4gdm9pZFxufVxuIl0sCiAgIm1hcHBpbmdzIjogIkFBa0JVO0FBbEJWLFNBQVMsVUFBVTtBQUVaLGdCQUFTLFFBQVEsRUFBRSxXQUFXLE9BQU8sWUFBWSxHQUFHLEtBQUssR0FBaUI7QUFDL0UsU0FDRSxvQkFBQyxTQUFJLFdBQVcsR0FBRywyQkFBMkIsU0FBUyxHQUFJLEdBQUcsTUFDM0QsZ0JBQU0sSUFBSSxDQUFDLEVBQUUsV0FBVyxNQUFNLE1BQU0sTUFBTSxNQUFNLE9BQU8sUUFBUSxNQUM5RDtBQUFBLElBQUM7QUFBQTtBQUFBLE1BQ0MsV0FBVTtBQUFBLE1BQ1Y7QUFBQSxNQUVBLFNBQVMsT0FBSztBQUNaLGtCQUFVLENBQUM7QUFDWCxxQkFBYTtBQUFBLE1BQ2Y7QUFBQSxNQUNBLEtBQUssV0FBVyx3QkFBd0I7QUFBQSxNQUN4QyxRQUFRLFdBQVcsV0FBVztBQUFBLE1BQzlCLE9BQU87QUFBQSxNQUVQLDhCQUFDLFFBQUs7QUFBQTtBQUFBLElBVEQ7QUFBQSxFQVVQLENBQ0QsR0FDSDtBQUVKOyIsCiAgIm5hbWVzIjogW10KfQo=
