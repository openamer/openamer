"use client";
import { jsx } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "../../utils/index.js";
export function Toast({ toast }) {
  const [visible, setVisible] = useState(false);
  const [current, setCurrent] = useState(toast);
  useEffect(() => {
    if (toast) {
      setCurrent(toast);
      setVisible(true);
    } else {
      setVisible(false);
      const timer = setTimeout(() => setCurrent(null), 200);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  if (!current || typeof document === "undefined") return null;
  return createPortal(
    /* @__PURE__ */ jsx(
      "div",
      {
        "aria-live": "polite",
        className: cn(
          "fixed top-16 right-4 z-50 border px-4 py-2.5 font-courier text-xs tracking-wider uppercase backdrop-blur-sm",
          current.type === "success" ? "bg-success/15 text-success border-success/30" : "bg-destructive/15 text-destructive border-destructive/30"
        ),
        role: "status",
        style: {
          animation: visible ? "toast-in 200ms ease-out forwards" : "toast-out 200ms ease-in forwards"
        },
        children: current.message
      }
    ),
    document.body
  );
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZUVmZmVjdCwgdXNlU3RhdGUgfSBmcm9tICdyZWFjdCdcbmltcG9ydCB7IGNyZWF0ZVBvcnRhbCB9IGZyb20gJ3JlYWN0LWRvbSdcblxuaW1wb3J0IHsgY24gfSBmcm9tICcuLi8uLi91dGlscydcblxuZXhwb3J0IGZ1bmN0aW9uIFRvYXN0KHsgdG9hc3QgfTogVG9hc3RQcm9wcykge1xuICBjb25zdCBbdmlzaWJsZSwgc2V0VmlzaWJsZV0gPSB1c2VTdGF0ZShmYWxzZSlcbiAgY29uc3QgW2N1cnJlbnQsIHNldEN1cnJlbnRdID0gdXNlU3RhdGUodG9hc3QpXG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBpZiAodG9hc3QpIHtcbiAgICAgIHNldEN1cnJlbnQodG9hc3QpXG4gICAgICBzZXRWaXNpYmxlKHRydWUpXG4gICAgfSBlbHNlIHtcbiAgICAgIHNldFZpc2libGUoZmFsc2UpXG4gICAgICBjb25zdCB0aW1lciA9IHNldFRpbWVvdXQoKCkgPT4gc2V0Q3VycmVudChudWxsKSwgMjAwKVxuICAgICAgcmV0dXJuICgpID0+IGNsZWFyVGltZW91dCh0aW1lcilcbiAgICB9XG4gIH0sIFt0b2FzdF0pXG5cbiAgaWYgKCFjdXJyZW50IHx8IHR5cGVvZiBkb2N1bWVudCA9PT0gJ3VuZGVmaW5lZCcpIHJldHVybiBudWxsXG5cbiAgcmV0dXJuIGNyZWF0ZVBvcnRhbChcbiAgICA8ZGl2XG4gICAgICBhcmlhLWxpdmU9XCJwb2xpdGVcIlxuICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgJ2ZpeGVkIHRvcC0xNiByaWdodC00IHotNTAgYm9yZGVyIHB4LTQgcHktMi41IGZvbnQtY291cmllciB0ZXh0LXhzIHRyYWNraW5nLXdpZGVyIHVwcGVyY2FzZSBiYWNrZHJvcC1ibHVyLXNtJyxcbiAgICAgICAgY3VycmVudC50eXBlID09PSAnc3VjY2VzcydcbiAgICAgICAgICA/ICdiZy1zdWNjZXNzLzE1IHRleHQtc3VjY2VzcyBib3JkZXItc3VjY2Vzcy8zMCdcbiAgICAgICAgICA6ICdiZy1kZXN0cnVjdGl2ZS8xNSB0ZXh0LWRlc3RydWN0aXZlIGJvcmRlci1kZXN0cnVjdGl2ZS8zMCdcbiAgICAgICl9XG4gICAgICByb2xlPVwic3RhdHVzXCJcbiAgICAgIHN0eWxlPXt7XG4gICAgICAgIGFuaW1hdGlvbjogdmlzaWJsZVxuICAgICAgICAgID8gJ3RvYXN0LWluIDIwMG1zIGVhc2Utb3V0IGZvcndhcmRzJ1xuICAgICAgICAgIDogJ3RvYXN0LW91dCAyMDBtcyBlYXNlLWluIGZvcndhcmRzJ1xuICAgICAgfX1cbiAgICA+XG4gICAgICB7Y3VycmVudC5tZXNzYWdlfVxuICAgIDwvZGl2PixcbiAgICBkb2N1bWVudC5ib2R5XG4gIClcbn1cblxuaW50ZXJmYWNlIFRvYXN0UHJvcHMge1xuICB0b2FzdDogeyBtZXNzYWdlOiBzdHJpbmc7IHR5cGU6ICdlcnJvcicgfCAnc3VjY2VzcycgfSB8IG51bGxcbn1cbiJdLAogICJtYXBwaW5ncyI6ICI7QUF5Qkk7QUF2QkosU0FBUyxXQUFXLGdCQUFnQjtBQUNwQyxTQUFTLG9CQUFvQjtBQUU3QixTQUFTLFVBQVU7QUFFWixnQkFBUyxNQUFNLEVBQUUsTUFBTSxHQUFlO0FBQzNDLFFBQU0sQ0FBQyxTQUFTLFVBQVUsSUFBSSxTQUFTLEtBQUs7QUFDNUMsUUFBTSxDQUFDLFNBQVMsVUFBVSxJQUFJLFNBQVMsS0FBSztBQUU1QyxZQUFVLE1BQU07QUFDZCxRQUFJLE9BQU87QUFDVCxpQkFBVyxLQUFLO0FBQ2hCLGlCQUFXLElBQUk7QUFBQSxJQUNqQixPQUFPO0FBQ0wsaUJBQVcsS0FBSztBQUNoQixZQUFNLFFBQVEsV0FBVyxNQUFNLFdBQVcsSUFBSSxHQUFHLEdBQUc7QUFDcEQsYUFBTyxNQUFNLGFBQWEsS0FBSztBQUFBLElBQ2pDO0FBQUEsRUFDRixHQUFHLENBQUMsS0FBSyxDQUFDO0FBRVYsTUFBSSxDQUFDLFdBQVcsT0FBTyxhQUFhLFlBQWEsUUFBTztBQUV4RCxTQUFPO0FBQUEsSUFDTDtBQUFBLE1BQUM7QUFBQTtBQUFBLFFBQ0MsYUFBVTtBQUFBLFFBQ1YsV0FBVztBQUFBLFVBQ1Q7QUFBQSxVQUNBLFFBQVEsU0FBUyxZQUNiLGlEQUNBO0FBQUEsUUFDTjtBQUFBLFFBQ0EsTUFBSztBQUFBLFFBQ0wsT0FBTztBQUFBLFVBQ0wsV0FBVyxVQUNQLHFDQUNBO0FBQUEsUUFDTjtBQUFBLFFBRUMsa0JBQVE7QUFBQTtBQUFBLElBQ1g7QUFBQSxJQUNBLFNBQVM7QUFBQSxFQUNYO0FBQ0Y7IiwKICAibmFtZXMiOiBbXQp9Cg==
