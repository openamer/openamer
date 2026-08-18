"use client";
import { jsx } from "react/jsx-runtime";
import { Leva } from "leva";
import { useEffect, useState } from "react";
export function LevaClient() {
  const [hidden, setHidden] = useState(true);
  useEffect(() => {
    setHidden(!new URLSearchParams(window.location.search).has("dev"));
  }, []);
  return /* @__PURE__ */ jsx(Leva, { ...{ hidden } });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IExldmEgfSBmcm9tICdsZXZhJ1xuaW1wb3J0IHsgdXNlRWZmZWN0LCB1c2VTdGF0ZSB9IGZyb20gJ3JlYWN0J1xuXG5leHBvcnQgZnVuY3Rpb24gTGV2YUNsaWVudCgpIHtcbiAgY29uc3QgW2hpZGRlbiwgc2V0SGlkZGVuXSA9IHVzZVN0YXRlKHRydWUpXG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBzZXRIaWRkZW4oIW5ldyBVUkxTZWFyY2hQYXJhbXMod2luZG93LmxvY2F0aW9uLnNlYXJjaCkuaGFzKCdkZXYnKSlcbiAgfSwgW10pXG5cbiAgcmV0dXJuIDxMZXZhIHsuLi57IGhpZGRlbiB9fSAvPlxufVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQVlTO0FBVlQsU0FBUyxZQUFZO0FBQ3JCLFNBQVMsV0FBVyxnQkFBZ0I7QUFFN0IsZ0JBQVMsYUFBYTtBQUMzQixRQUFNLENBQUMsUUFBUSxTQUFTLElBQUksU0FBUyxJQUFJO0FBRXpDLFlBQVUsTUFBTTtBQUNkLGNBQVUsQ0FBQyxJQUFJLGdCQUFnQixPQUFPLFNBQVMsTUFBTSxFQUFFLElBQUksS0FBSyxDQUFDO0FBQUEsRUFDbkUsR0FBRyxDQUFDLENBQUM7QUFFTCxTQUFPLG9CQUFDLFFBQU0sR0FBRyxFQUFFLE9BQU8sR0FBRztBQUMvQjsiLAogICJuYW1lcyI6IFtdCn0K
