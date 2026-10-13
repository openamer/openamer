import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { Cell, Grid } from "./components/grid/index.js";
import { Progress } from "./components/progress.js";
import { H1 } from "./components/typography/h1.js";
import { Small } from "./components/typography/small.js";
export function BasicPage({ children, subtitle, title }) {
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(Grid, { children: /* @__PURE__ */ jsx(Cell, { children: /* @__PURE__ */ jsx(Progress, { value: 0 }) }) }),
    /* @__PURE__ */ jsxs(Grid, { className: "lg:grid-cols-[max-content_1fr]", children: [
      /* @__PURE__ */ jsx(Cell, { className: "-order-1", children: /* @__PURE__ */ jsxs("div", { className: "sticky top-4 flex flex-col gap-4", children: [
        title ? /* @__PURE__ */ jsx(H1, { className: "-mb-2 pr-10 opacity-90", children: title }) : null,
        subtitle ? /* @__PURE__ */ jsx(Small, { className: "opacity-60", children: subtitle }) : null
      ] }) }),
      /* @__PURE__ */ jsx(Cell, { className: "post bg-current/3", children })
    ] })
  ] });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHR5cGUgeyBSZWFjdE5vZGUgfSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IHsgQ2VsbCwgR3JpZCB9IGZyb20gJy4vY29tcG9uZW50cy9ncmlkJ1xuaW1wb3J0IHsgUHJvZ3Jlc3MgfSBmcm9tICcuL2NvbXBvbmVudHMvcHJvZ3Jlc3MnXG5pbXBvcnQgeyBIMSB9IGZyb20gJy4vY29tcG9uZW50cy90eXBvZ3JhcGh5L2gxJ1xuaW1wb3J0IHsgU21hbGwgfSBmcm9tICcuL2NvbXBvbmVudHMvdHlwb2dyYXBoeS9zbWFsbCdcblxuZXhwb3J0IGZ1bmN0aW9uIEJhc2ljUGFnZSh7IGNoaWxkcmVuLCBzdWJ0aXRsZSwgdGl0bGUgfTogQmFzaWNQYWdlUHJvcHMpIHtcbiAgcmV0dXJuIChcbiAgICA8PlxuICAgICAgPEdyaWQ+XG4gICAgICAgIDxDZWxsPlxuICAgICAgICAgIDxQcm9ncmVzcyB2YWx1ZT17MH0gLz5cbiAgICAgICAgPC9DZWxsPlxuICAgICAgPC9HcmlkPlxuXG4gICAgICA8R3JpZCBjbGFzc05hbWU9XCJsZzpncmlkLWNvbHMtW21heC1jb250ZW50XzFmcl1cIj5cbiAgICAgICAgPENlbGwgY2xhc3NOYW1lPVwiLW9yZGVyLTFcIj5cbiAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cInN0aWNreSB0b3AtNCBmbGV4IGZsZXgtY29sIGdhcC00XCI+XG4gICAgICAgICAgICB7dGl0bGUgPyA8SDEgY2xhc3NOYW1lPVwiLW1iLTIgcHItMTAgb3BhY2l0eS05MFwiPnt0aXRsZX08L0gxPiA6IG51bGx9XG4gICAgICAgICAgICB7c3VidGl0bGUgPyA8U21hbGwgY2xhc3NOYW1lPVwib3BhY2l0eS02MFwiPntzdWJ0aXRsZX08L1NtYWxsPiA6IG51bGx9XG4gICAgICAgICAgPC9kaXY+XG4gICAgICAgIDwvQ2VsbD5cblxuICAgICAgICA8Q2VsbCBjbGFzc05hbWU9XCJwb3N0IGJnLWN1cnJlbnQvM1wiPntjaGlsZHJlbn08L0NlbGw+XG4gICAgICA8L0dyaWQ+XG4gICAgPC8+XG4gIClcbn1cblxuaW50ZXJmYWNlIEJhc2ljUGFnZVByb3BzIGV4dGVuZHMgUmVhY3QuUHJvcHNXaXRoQ2hpbGRyZW4ge1xuICBzdWJ0aXRsZT86IHN0cmluZ1xuICB0aXRsZT86IFJlYWN0Tm9kZVxufVxuIl0sCiAgIm1hcHBpbmdzIjogIkFBU0ksbUJBR00sS0FNQSxZQVROO0FBUEosU0FBUyxNQUFNLFlBQVk7QUFDM0IsU0FBUyxnQkFBZ0I7QUFDekIsU0FBUyxVQUFVO0FBQ25CLFNBQVMsYUFBYTtBQUVmLGdCQUFTLFVBQVUsRUFBRSxVQUFVLFVBQVUsTUFBTSxHQUFtQjtBQUN2RSxTQUNFLGlDQUNFO0FBQUEsd0JBQUMsUUFDQyw4QkFBQyxRQUNDLDhCQUFDLFlBQVMsT0FBTyxHQUFHLEdBQ3RCLEdBQ0Y7QUFBQSxJQUVBLHFCQUFDLFFBQUssV0FBVSxrQ0FDZDtBQUFBLDBCQUFDLFFBQUssV0FBVSxZQUNkLCtCQUFDLFNBQUksV0FBVSxvQ0FDWjtBQUFBLGdCQUFRLG9CQUFDLE1BQUcsV0FBVSwwQkFBMEIsaUJBQU0sSUFBUTtBQUFBLFFBQzlELFdBQVcsb0JBQUMsU0FBTSxXQUFVLGNBQWMsb0JBQVMsSUFBVztBQUFBLFNBQ2pFLEdBQ0Y7QUFBQSxNQUVBLG9CQUFDLFFBQUssV0FBVSxxQkFBcUIsVUFBUztBQUFBLE9BQ2hEO0FBQUEsS0FDRjtBQUVKOyIsCiAgIm5hbWVzIjogW10KfQo=
