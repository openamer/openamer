"use client";
import { jsx } from "react/jsx-runtime";
import { cn } from "../../utils/index.js";
export function Blink({ className, cursor = "block" }) {
  return /* @__PURE__ */ jsx(
    "span",
    {
      className: cn(
        "blink hidden group-hover:inline-block",
        "dither ml-1 w-[1.2ch]",
        cursor === "block" ? "-mb-[0.15em] h-[1.1em]" : "-mb-[0.1em] h-[2px]",
        className
      )
    }
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IGNuIH0gZnJvbSAnLi4vLi4vdXRpbHMnXG5cbmV4cG9ydCBmdW5jdGlvbiBCbGluayh7IGNsYXNzTmFtZSwgY3Vyc29yID0gJ2Jsb2NrJyB9OiBCbGlua1Byb3BzKSB7XG4gIHJldHVybiAoXG4gICAgPHNwYW5cbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICdibGluayBoaWRkZW4gZ3JvdXAtaG92ZXI6aW5saW5lLWJsb2NrJyxcbiAgICAgICAgJ2RpdGhlciBtbC0xIHctWzEuMmNoXScsXG4gICAgICAgIGN1cnNvciA9PT0gJ2Jsb2NrJyA/ICctbWItWzAuMTVlbV0gaC1bMS4xZW1dJyA6ICctbWItWzAuMWVtXSBoLVsycHhdJyxcbiAgICAgICAgY2xhc3NOYW1lXG4gICAgICApfVxuICAgIC8+XG4gIClcbn1cblxuaW50ZXJmYWNlIEJsaW5rUHJvcHMge1xuICBjbGFzc05hbWU/OiBzdHJpbmdcbiAgY3Vyc29yPzogJ2Jsb2NrJyB8ICdsaW5lJ1xufVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQU1JO0FBSkosU0FBUyxVQUFVO0FBRVosZ0JBQVMsTUFBTSxFQUFFLFdBQVcsU0FBUyxRQUFRLEdBQWU7QUFDakUsU0FDRTtBQUFBLElBQUM7QUFBQTtBQUFBLE1BQ0MsV0FBVztBQUFBLFFBQ1Q7QUFBQSxRQUNBO0FBQUEsUUFDQSxXQUFXLFVBQVUsMkJBQTJCO0FBQUEsUUFDaEQ7QUFBQSxNQUNGO0FBQUE7QUFBQSxFQUNGO0FBRUo7IiwKICAibmFtZXMiOiBbXQp9Cg==
