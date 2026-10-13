"use client";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { cn } from "../../utils/index.js";
import { Scramble } from "./ascii.js";
import { LinkIcon } from "./icons/index.js";
import { Typography } from "./typography/index.js";
const ETH_RE = /^0x[a-fA-F0-9]{40}$/;
const truncate = (a) => `${a.slice(0, 6)}${"\xB7".repeat(8)}${a.slice(-4)}`;
export function Watchlist({
  className,
  counter = false,
  items,
  scramble = false,
  ...props
}) {
  return /* @__PURE__ */ jsx("div", { className: cn("flex flex-col gap-3", className), ...props, children: items.map(({ label, right, url }, i) => {
    const isStr = typeof label === "string";
    const eth = isStr && ETH_RE.test(label);
    const text = eth ? truncate(label) : label;
    return /* @__PURE__ */ jsxs(
      "a",
      {
        className: cn(
          "grid items-center gap-2.5 px-2.5 py-1.5",
          "text-display leading-[1.4]",
          "hover:bg-midground/10! hover:ring-2 hover:ring-current/20",
          "transition-all duration-500 hover:duration-0",
          "opacity-(--midground-alpha)"
        ),
        href: url,
        rel: "noopener noreferrer",
        style: {
          background: `color-mix(in oklch, var(--color-midground) ${10 * Math.max(0, 1 - i / 9)}%, transparent)`,
          gridTemplateColumns: [
            counter && "auto auto",
            "1fr",
            right && "auto",
            url && "auto auto"
          ].filter(Boolean).join(" ")
        },
        target: "_blank",
        children: [
          counter && /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx(
              Typography,
              {
                className: "text-lg tracking-[0.35em] opacity-40",
                compressed: true,
                children: String(i + 1).padStart(2, "0")
              }
            ),
            /* @__PURE__ */ jsx("span", { className: "text-[0.8125rem] font-bold tracking-[0.4em] opacity-20", children: ":" })
          ] }),
          isStr ? /* @__PURE__ */ jsx(
            Typography,
            {
              className: "min-w-0 overflow-hidden text-lg font-bold tracking-[0.35em]",
              ...eth ? { mono: true } : { compressed: true },
              children: scramble ? /* @__PURE__ */ jsx(Scramble, { delay: i * 80, text }) : text
            }
          ) : label,
          right && /* @__PURE__ */ jsx(
            Typography,
            {
              className: "text-right text-sm tracking-widest opacity-40",
              mono: true,
              children: right
            }
          ),
          url && /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx("span", { className: "text-[0.8125rem] tracking-[0.4em] opacity-20", children: ":" }),
            /* @__PURE__ */ jsx(LinkIcon, { className: "text-midground size-3.5" })
          ] })
        ]
      },
      i
    );
  }) });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IGNuIH0gZnJvbSAnLi4vLi4vdXRpbHMnXG5cbmltcG9ydCB7IFNjcmFtYmxlIH0gZnJvbSAnLi9hc2NpaSdcbmltcG9ydCB7IExpbmtJY29uIH0gZnJvbSAnLi9pY29ucydcbmltcG9ydCB7IFR5cG9ncmFwaHkgfSBmcm9tICcuL3R5cG9ncmFwaHknXG5cbmNvbnN0IEVUSF9SRSA9IC9eMHhbYS1mQS1GMC05XXs0MH0kL1xuY29uc3QgdHJ1bmNhdGUgPSAoYTogc3RyaW5nKSA9PiBgJHthLnNsaWNlKDAsIDYpfSR7J1x1MDBCNycucmVwZWF0KDgpfSR7YS5zbGljZSgtNCl9YFxuXG5leHBvcnQgZnVuY3Rpb24gV2F0Y2hsaXN0KHtcbiAgY2xhc3NOYW1lLFxuICBjb3VudGVyID0gZmFsc2UsXG4gIGl0ZW1zLFxuICBzY3JhbWJsZSA9IGZhbHNlLFxuICAuLi5wcm9wc1xufTogV2F0Y2hsaXN0UHJvcHMpIHtcbiAgcmV0dXJuIChcbiAgICA8ZGl2IGNsYXNzTmFtZT17Y24oJ2ZsZXggZmxleC1jb2wgZ2FwLTMnLCBjbGFzc05hbWUpfSB7Li4ucHJvcHN9PlxuICAgICAge2l0ZW1zLm1hcCgoeyBsYWJlbCwgcmlnaHQsIHVybCB9LCBpKSA9PiB7XG4gICAgICAgIGNvbnN0IGlzU3RyID0gdHlwZW9mIGxhYmVsID09PSAnc3RyaW5nJ1xuICAgICAgICBjb25zdCBldGggPSBpc1N0ciAmJiBFVEhfUkUudGVzdChsYWJlbClcbiAgICAgICAgY29uc3QgdGV4dCA9IGV0aCA/IHRydW5jYXRlKGxhYmVsKSA6IChsYWJlbCBhcyBzdHJpbmcpXG5cbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICA8YVxuICAgICAgICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgICAgICAgJ2dyaWQgaXRlbXMtY2VudGVyIGdhcC0yLjUgcHgtMi41IHB5LTEuNScsXG4gICAgICAgICAgICAgICd0ZXh0LWRpc3BsYXkgbGVhZGluZy1bMS40XScsXG4gICAgICAgICAgICAgICdob3ZlcjpiZy1taWRncm91bmQvMTAhIGhvdmVyOnJpbmctMiBob3ZlcjpyaW5nLWN1cnJlbnQvMjAnLFxuICAgICAgICAgICAgICAndHJhbnNpdGlvbi1hbGwgZHVyYXRpb24tNTAwIGhvdmVyOmR1cmF0aW9uLTAnLFxuICAgICAgICAgICAgICAnb3BhY2l0eS0oLS1taWRncm91bmQtYWxwaGEpJ1xuICAgICAgICAgICAgKX1cbiAgICAgICAgICAgIGhyZWY9e3VybH1cbiAgICAgICAgICAgIGtleT17aX1cbiAgICAgICAgICAgIHJlbD1cIm5vb3BlbmVyIG5vcmVmZXJyZXJcIlxuICAgICAgICAgICAgc3R5bGU9e3tcbiAgICAgICAgICAgICAgYmFja2dyb3VuZDogYGNvbG9yLW1peChpbiBva2xjaCwgdmFyKC0tY29sb3ItbWlkZ3JvdW5kKSAkezEwICogTWF0aC5tYXgoMCwgMSAtIGkgLyA5KX0lLCB0cmFuc3BhcmVudClgLFxuICAgICAgICAgICAgICBncmlkVGVtcGxhdGVDb2x1bW5zOiBbXG4gICAgICAgICAgICAgICAgY291bnRlciAmJiAnYXV0byBhdXRvJyxcbiAgICAgICAgICAgICAgICAnMWZyJyxcbiAgICAgICAgICAgICAgICByaWdodCAmJiAnYXV0bycsXG4gICAgICAgICAgICAgICAgdXJsICYmICdhdXRvIGF1dG8nXG4gICAgICAgICAgICAgIF1cbiAgICAgICAgICAgICAgICAuZmlsdGVyKEJvb2xlYW4pXG4gICAgICAgICAgICAgICAgLmpvaW4oJyAnKVxuICAgICAgICAgICAgfX1cbiAgICAgICAgICAgIHRhcmdldD1cIl9ibGFua1wiXG4gICAgICAgICAgPlxuICAgICAgICAgICAge2NvdW50ZXIgJiYgKFxuICAgICAgICAgICAgICA8PlxuICAgICAgICAgICAgICAgIDxUeXBvZ3JhcGh5XG4gICAgICAgICAgICAgICAgICBjbGFzc05hbWU9XCJ0ZXh0LWxnIHRyYWNraW5nLVswLjM1ZW1dIG9wYWNpdHktNDBcIlxuICAgICAgICAgICAgICAgICAgY29tcHJlc3NlZFxuICAgICAgICAgICAgICAgID5cbiAgICAgICAgICAgICAgICAgIHtTdHJpbmcoaSArIDEpLnBhZFN0YXJ0KDIsICcwJyl9XG4gICAgICAgICAgICAgICAgPC9UeXBvZ3JhcGh5PlxuXG4gICAgICAgICAgICAgICAgPHNwYW4gY2xhc3NOYW1lPVwidGV4dC1bMC44MTI1cmVtXSBmb250LWJvbGQgdHJhY2tpbmctWzAuNGVtXSBvcGFjaXR5LTIwXCI+XG4gICAgICAgICAgICAgICAgICA6XG4gICAgICAgICAgICAgICAgPC9zcGFuPlxuICAgICAgICAgICAgICA8Lz5cbiAgICAgICAgICAgICl9XG5cbiAgICAgICAgICAgIHtpc1N0ciA/IChcbiAgICAgICAgICAgICAgPFR5cG9ncmFwaHlcbiAgICAgICAgICAgICAgICBjbGFzc05hbWU9XCJtaW4tdy0wIG92ZXJmbG93LWhpZGRlbiB0ZXh0LWxnIGZvbnQtYm9sZCB0cmFja2luZy1bMC4zNWVtXVwiXG4gICAgICAgICAgICAgICAgey4uLihldGggPyB7IG1vbm86IHRydWUgfSA6IHsgY29tcHJlc3NlZDogdHJ1ZSB9KX1cbiAgICAgICAgICAgICAgPlxuICAgICAgICAgICAgICAgIHtzY3JhbWJsZSA/IDxTY3JhbWJsZSBkZWxheT17aSAqIDgwfSB0ZXh0PXt0ZXh0fSAvPiA6IHRleHR9XG4gICAgICAgICAgICAgIDwvVHlwb2dyYXBoeT5cbiAgICAgICAgICAgICkgOiAoXG4gICAgICAgICAgICAgIGxhYmVsXG4gICAgICAgICAgICApfVxuXG4gICAgICAgICAgICB7cmlnaHQgJiYgKFxuICAgICAgICAgICAgICA8VHlwb2dyYXBoeVxuICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cInRleHQtcmlnaHQgdGV4dC1zbSB0cmFja2luZy13aWRlc3Qgb3BhY2l0eS00MFwiXG4gICAgICAgICAgICAgICAgbW9ub1xuICAgICAgICAgICAgICA+XG4gICAgICAgICAgICAgICAge3JpZ2h0fVxuICAgICAgICAgICAgICA8L1R5cG9ncmFwaHk+XG4gICAgICAgICAgICApfVxuXG4gICAgICAgICAgICB7dXJsICYmIChcbiAgICAgICAgICAgICAgPD5cbiAgICAgICAgICAgICAgICA8c3BhbiBjbGFzc05hbWU9XCJ0ZXh0LVswLjgxMjVyZW1dIHRyYWNraW5nLVswLjRlbV0gb3BhY2l0eS0yMFwiPlxuICAgICAgICAgICAgICAgICAgOlxuICAgICAgICAgICAgICAgIDwvc3Bhbj5cbiAgICAgICAgICAgICAgICA8TGlua0ljb24gY2xhc3NOYW1lPVwidGV4dC1taWRncm91bmQgc2l6ZS0zLjVcIiAvPlxuICAgICAgICAgICAgICA8Lz5cbiAgICAgICAgICAgICl9XG4gICAgICAgICAgPC9hPlxuICAgICAgICApXG4gICAgICB9KX1cbiAgICA8L2Rpdj5cbiAgKVxufVxuXG5pbnRlcmZhY2UgV2F0Y2hsaXN0UHJvcHMgZXh0ZW5kcyBSZWFjdC5Db21wb25lbnRQcm9wczwnZGl2Jz4ge1xuICBjb3VudGVyPzogYm9vbGVhblxuICBpdGVtczogeyBsYWJlbD86IFJlYWN0LlJlYWN0Tm9kZTsgcmlnaHQ/OiBSZWFjdC5SZWFjdE5vZGU7IHVybD86IHN0cmluZyB9W11cbiAgc2NyYW1ibGU/OiBib29sZWFuXG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBbURjLG1CQUNFLEtBREY7QUFqRGQsU0FBUyxVQUFVO0FBRW5CLFNBQVMsZ0JBQWdCO0FBQ3pCLFNBQVMsZ0JBQWdCO0FBQ3pCLFNBQVMsa0JBQWtCO0FBRTNCLE1BQU0sU0FBUztBQUNmLE1BQU0sV0FBVyxDQUFDLE1BQWMsR0FBRyxFQUFFLE1BQU0sR0FBRyxDQUFDLENBQUMsR0FBRyxPQUFJLE9BQU8sQ0FBQyxDQUFDLEdBQUcsRUFBRSxNQUFNLEVBQUUsQ0FBQztBQUV2RSxnQkFBUyxVQUFVO0FBQUEsRUFDeEI7QUFBQSxFQUNBLFVBQVU7QUFBQSxFQUNWO0FBQUEsRUFDQSxXQUFXO0FBQUEsRUFDWCxHQUFHO0FBQ0wsR0FBbUI7QUFDakIsU0FDRSxvQkFBQyxTQUFJLFdBQVcsR0FBRyx1QkFBdUIsU0FBUyxHQUFJLEdBQUcsT0FDdkQsZ0JBQU0sSUFBSSxDQUFDLEVBQUUsT0FBTyxPQUFPLElBQUksR0FBRyxNQUFNO0FBQ3ZDLFVBQU0sUUFBUSxPQUFPLFVBQVU7QUFDL0IsVUFBTSxNQUFNLFNBQVMsT0FBTyxLQUFLLEtBQUs7QUFDdEMsVUFBTSxPQUFPLE1BQU0sU0FBUyxLQUFLLElBQUs7QUFFdEMsV0FDRTtBQUFBLE1BQUM7QUFBQTtBQUFBLFFBQ0MsV0FBVztBQUFBLFVBQ1Q7QUFBQSxVQUNBO0FBQUEsVUFDQTtBQUFBLFVBQ0E7QUFBQSxVQUNBO0FBQUEsUUFDRjtBQUFBLFFBQ0EsTUFBTTtBQUFBLFFBRU4sS0FBSTtBQUFBLFFBQ0osT0FBTztBQUFBLFVBQ0wsWUFBWSw4Q0FBOEMsS0FBSyxLQUFLLElBQUksR0FBRyxJQUFJLElBQUksQ0FBQyxDQUFDO0FBQUEsVUFDckYscUJBQXFCO0FBQUEsWUFDbkIsV0FBVztBQUFBLFlBQ1g7QUFBQSxZQUNBLFNBQVM7QUFBQSxZQUNULE9BQU87QUFBQSxVQUNULEVBQ0csT0FBTyxPQUFPLEVBQ2QsS0FBSyxHQUFHO0FBQUEsUUFDYjtBQUFBLFFBQ0EsUUFBTztBQUFBLFFBRU47QUFBQSxxQkFDQyxpQ0FDRTtBQUFBO0FBQUEsY0FBQztBQUFBO0FBQUEsZ0JBQ0MsV0FBVTtBQUFBLGdCQUNWLFlBQVU7QUFBQSxnQkFFVCxpQkFBTyxJQUFJLENBQUMsRUFBRSxTQUFTLEdBQUcsR0FBRztBQUFBO0FBQUEsWUFDaEM7QUFBQSxZQUVBLG9CQUFDLFVBQUssV0FBVSwwREFBeUQsZUFFekU7QUFBQSxhQUNGO0FBQUEsVUFHRCxRQUNDO0FBQUEsWUFBQztBQUFBO0FBQUEsY0FDQyxXQUFVO0FBQUEsY0FDVCxHQUFJLE1BQU0sRUFBRSxNQUFNLEtBQUssSUFBSSxFQUFFLFlBQVksS0FBSztBQUFBLGNBRTlDLHFCQUFXLG9CQUFDLFlBQVMsT0FBTyxJQUFJLElBQUksTUFBWSxJQUFLO0FBQUE7QUFBQSxVQUN4RCxJQUVBO0FBQUEsVUFHRCxTQUNDO0FBQUEsWUFBQztBQUFBO0FBQUEsY0FDQyxXQUFVO0FBQUEsY0FDVixNQUFJO0FBQUEsY0FFSDtBQUFBO0FBQUEsVUFDSDtBQUFBLFVBR0QsT0FDQyxpQ0FDRTtBQUFBLGdDQUFDLFVBQUssV0FBVSxnREFBK0MsZUFFL0Q7QUFBQSxZQUNBLG9CQUFDLFlBQVMsV0FBVSwyQkFBMEI7QUFBQSxhQUNoRDtBQUFBO0FBQUE7QUFBQSxNQXhERztBQUFBLElBMERQO0FBQUEsRUFFSixDQUFDLEdBQ0g7QUFFSjsiLAogICJuYW1lcyI6IFtdCn0K
