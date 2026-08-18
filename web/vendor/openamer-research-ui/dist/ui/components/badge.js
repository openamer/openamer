import { jsx } from "react/jsx-runtime";
import { cn } from "../../utils/index.js";
import { BlendMode } from "./blend-mode.js";
const BASE_CN = "inline-flex items-center font-compressed text-display px-2 py-1 leading-none tracking-[0.2em]";
const TONE_CLASSES = {
  destructive: "border border-destructive/30 bg-destructive/15 text-destructive",
  outline: "border border-midground/30 bg-transparent text-midground/80",
  secondary: "border border-midground/15 bg-midground/8 text-midground",
  success: "border border-success/30 bg-success/15 text-success",
  warning: "border border-warning/30 bg-warning/15 text-warning"
};
export const Badge = ({
  className,
  style,
  tone = "default",
  ...props
}) => {
  if (tone === "default") {
    return /* @__PURE__ */ jsx(
      BlendMode,
      {
        as: "span",
        background: "mg/0.075",
        className: cn(BASE_CN, className),
        color: "mg",
        style: { opacity: "var(--midground-alpha)", ...style },
        ...props
      }
    );
  }
  return /* @__PURE__ */ jsx(
    "span",
    {
      className: cn(BASE_CN, TONE_CLASSES[tone], className),
      style,
      ...props
    }
  );
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuaW1wb3J0IHsgQmxlbmRNb2RlLCB0eXBlIEJsZW5kTW9kZVByb3BzIH0gZnJvbSAnLi9ibGVuZC1tb2RlJ1xuXG5jb25zdCBCQVNFX0NOID1cbiAgJ2lubGluZS1mbGV4IGl0ZW1zLWNlbnRlciBmb250LWNvbXByZXNzZWQgdGV4dC1kaXNwbGF5IHB4LTIgcHktMSBsZWFkaW5nLW5vbmUgdHJhY2tpbmctWzAuMmVtXSdcblxuY29uc3QgVE9ORV9DTEFTU0VTOiBSZWNvcmQ8RXhjbHVkZTxUb25lLCAnZGVmYXVsdCc+LCBzdHJpbmc+ID0ge1xuICBkZXN0cnVjdGl2ZTpcbiAgICAnYm9yZGVyIGJvcmRlci1kZXN0cnVjdGl2ZS8zMCBiZy1kZXN0cnVjdGl2ZS8xNSB0ZXh0LWRlc3RydWN0aXZlJyxcbiAgb3V0bGluZTogJ2JvcmRlciBib3JkZXItbWlkZ3JvdW5kLzMwIGJnLXRyYW5zcGFyZW50IHRleHQtbWlkZ3JvdW5kLzgwJyxcbiAgc2Vjb25kYXJ5OiAnYm9yZGVyIGJvcmRlci1taWRncm91bmQvMTUgYmctbWlkZ3JvdW5kLzggdGV4dC1taWRncm91bmQnLFxuICBzdWNjZXNzOiAnYm9yZGVyIGJvcmRlci1zdWNjZXNzLzMwIGJnLXN1Y2Nlc3MvMTUgdGV4dC1zdWNjZXNzJyxcbiAgd2FybmluZzogJ2JvcmRlciBib3JkZXItd2FybmluZy8zMCBiZy13YXJuaW5nLzE1IHRleHQtd2FybmluZydcbn1cblxuZXhwb3J0IGNvbnN0IEJhZGdlID0gKHtcbiAgY2xhc3NOYW1lLFxuICBzdHlsZSxcbiAgdG9uZSA9ICdkZWZhdWx0JyxcbiAgLi4ucHJvcHNcbn06IEJhZGdlUHJvcHMpID0+IHtcbiAgLy8gYHRvbmU9XCJkZWZhdWx0XCJgIGtlZXBzIHRoZSBvcmlnaW5hbCBMZW5zLWF3YXJlIEJsZW5kTW9kZSB0cmVhdG1lbnQgc29cbiAgLy8gZXhpc3RpbmcgYnJhbmQtc3R5bGUgY29uc3VtZXJzIChub3VzbmV0LXdlYiBldGMuKSByZW5kZXIgdW5jaGFuZ2VkLlxuICBpZiAodG9uZSA9PT0gJ2RlZmF1bHQnKSB7XG4gICAgcmV0dXJuIChcbiAgICAgIDxCbGVuZE1vZGVcbiAgICAgICAgYXM9XCJzcGFuXCJcbiAgICAgICAgYmFja2dyb3VuZD1cIm1nLzAuMDc1XCJcbiAgICAgICAgY2xhc3NOYW1lPXtjbihCQVNFX0NOLCBjbGFzc05hbWUpfVxuICAgICAgICBjb2xvcj1cIm1nXCJcbiAgICAgICAgc3R5bGU9e3sgb3BhY2l0eTogJ3ZhcigtLW1pZGdyb3VuZC1hbHBoYSknLCAuLi5zdHlsZSB9fVxuICAgICAgICB7Li4uKHByb3BzIGFzIEJsZW5kTW9kZVByb3BzPCdzcGFuJz4pfVxuICAgICAgLz5cbiAgICApXG4gIH1cblxuICAvLyBTZW1hbnRpYyB0b25lcyBieXBhc3MgQmxlbmRNb2RlIGFuZCB1c2UgLS1jb2xvci0qIHRva2VucyBkaXJlY3RseSBzb1xuICAvLyByZWQgc3RheXMgcmVkIGFuZCBncmVlbiBzdGF5cyBncmVlbiByZWdhcmRsZXNzIG9mIHRoZSBhY3RpdmUgTGVucy5cbiAgcmV0dXJuIChcbiAgICA8c3BhblxuICAgICAgY2xhc3NOYW1lPXtjbihCQVNFX0NOLCBUT05FX0NMQVNTRVNbdG9uZV0sIGNsYXNzTmFtZSl9XG4gICAgICBzdHlsZT17c3R5bGV9XG4gICAgICB7Li4uKHByb3BzIGFzIFJlYWN0LkhUTUxBdHRyaWJ1dGVzPEhUTUxTcGFuRWxlbWVudD4pfVxuICAgIC8+XG4gIClcbn1cblxudHlwZSBUb25lID1cbiAgfCAnZGVmYXVsdCdcbiAgfCAnZGVzdHJ1Y3RpdmUnXG4gIHwgJ291dGxpbmUnXG4gIHwgJ3NlY29uZGFyeSdcbiAgfCAnc3VjY2VzcydcbiAgfCAnd2FybmluZydcblxuaW50ZXJmYWNlIEJhZGdlUHJvcHNcbiAgZXh0ZW5kcyBPbWl0PFJlYWN0LkhUTUxBdHRyaWJ1dGVzPEhUTUxTcGFuRWxlbWVudD4sICdjb2xvcic+IHtcbiAgdG9uZT86IFRvbmVcbn1cbiJdLAogICJtYXBwaW5ncyI6ICJBQTBCTTtBQTFCTixTQUFTLFVBQVU7QUFFbkIsU0FBUyxpQkFBc0M7QUFFL0MsTUFBTSxVQUNKO0FBRUYsTUFBTSxlQUF5RDtBQUFBLEVBQzdELGFBQ0U7QUFBQSxFQUNGLFNBQVM7QUFBQSxFQUNULFdBQVc7QUFBQSxFQUNYLFNBQVM7QUFBQSxFQUNULFNBQVM7QUFDWDtBQUVPLGFBQU0sUUFBUSxDQUFDO0FBQUEsRUFDcEI7QUFBQSxFQUNBO0FBQUEsRUFDQSxPQUFPO0FBQUEsRUFDUCxHQUFHO0FBQ0wsTUFBa0I7QUFHaEIsTUFBSSxTQUFTLFdBQVc7QUFDdEIsV0FDRTtBQUFBLE1BQUM7QUFBQTtBQUFBLFFBQ0MsSUFBRztBQUFBLFFBQ0gsWUFBVztBQUFBLFFBQ1gsV0FBVyxHQUFHLFNBQVMsU0FBUztBQUFBLFFBQ2hDLE9BQU07QUFBQSxRQUNOLE9BQU8sRUFBRSxTQUFTLDBCQUEwQixHQUFHLE1BQU07QUFBQSxRQUNwRCxHQUFJO0FBQUE7QUFBQSxJQUNQO0FBQUEsRUFFSjtBQUlBLFNBQ0U7QUFBQSxJQUFDO0FBQUE7QUFBQSxNQUNDLFdBQVcsR0FBRyxTQUFTLGFBQWEsSUFBSSxHQUFHLFNBQVM7QUFBQSxNQUNwRDtBQUFBLE1BQ0MsR0FBSTtBQUFBO0FBQUEsRUFDUDtBQUVKOyIsCiAgIm5hbWVzIjogW10KfQo=
