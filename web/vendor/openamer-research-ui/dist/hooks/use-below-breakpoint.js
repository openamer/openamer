"use client";
import { useEffect, useState } from "react";
export function useBelowBreakpoint(px) {
  const query = `(max-width: ${px - 1}px)`;
  const [matches, setMatches] = useState(
    () => typeof window !== "undefined" ? window.matchMedia(query).matches : false
  );
  useEffect(() => {
    const mql = window.matchMedia(query);
    const sync = () => setMatches(mql.matches);
    sync();
    mql.addEventListener("change", sync);
    return () => mql.removeEventListener("change", sync);
  }, [query]);
  return matches;
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZUVmZmVjdCwgdXNlU3RhdGUgfSBmcm9tICdyZWFjdCdcblxuLyoqIFRydWUgd2hlbiB2aWV3cG9ydCB3aWR0aCBpcyBzdHJpY3RseSBiZWxvdyBgcHhgLiAqL1xuZXhwb3J0IGZ1bmN0aW9uIHVzZUJlbG93QnJlYWtwb2ludChweDogbnVtYmVyKSB7XG4gIGNvbnN0IHF1ZXJ5ID0gYChtYXgtd2lkdGg6ICR7cHggLSAxfXB4KWBcbiAgY29uc3QgW21hdGNoZXMsIHNldE1hdGNoZXNdID0gdXNlU3RhdGUoKCkgPT5cbiAgICB0eXBlb2Ygd2luZG93ICE9PSAndW5kZWZpbmVkJyA/IHdpbmRvdy5tYXRjaE1lZGlhKHF1ZXJ5KS5tYXRjaGVzIDogZmFsc2VcbiAgKVxuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgY29uc3QgbXFsID0gd2luZG93Lm1hdGNoTWVkaWEocXVlcnkpXG4gICAgY29uc3Qgc3luYyA9ICgpID0+IHNldE1hdGNoZXMobXFsLm1hdGNoZXMpXG4gICAgc3luYygpXG4gICAgbXFsLmFkZEV2ZW50TGlzdGVuZXIoJ2NoYW5nZScsIHN5bmMpXG4gICAgcmV0dXJuICgpID0+IG1xbC5yZW1vdmVFdmVudExpc3RlbmVyKCdjaGFuZ2UnLCBzeW5jKVxuICB9LCBbcXVlcnldKVxuXG4gIHJldHVybiBtYXRjaGVzXG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBRUEsU0FBUyxXQUFXLGdCQUFnQjtBQUc3QixnQkFBUyxtQkFBbUIsSUFBWTtBQUM3QyxRQUFNLFFBQVEsZUFBZSxLQUFLLENBQUM7QUFDbkMsUUFBTSxDQUFDLFNBQVMsVUFBVSxJQUFJO0FBQUEsSUFBUyxNQUNyQyxPQUFPLFdBQVcsY0FBYyxPQUFPLFdBQVcsS0FBSyxFQUFFLFVBQVU7QUFBQSxFQUNyRTtBQUVBLFlBQVUsTUFBTTtBQUNkLFVBQU0sTUFBTSxPQUFPLFdBQVcsS0FBSztBQUNuQyxVQUFNLE9BQU8sTUFBTSxXQUFXLElBQUksT0FBTztBQUN6QyxTQUFLO0FBQ0wsUUFBSSxpQkFBaUIsVUFBVSxJQUFJO0FBQ25DLFdBQU8sTUFBTSxJQUFJLG9CQUFvQixVQUFVLElBQUk7QUFBQSxFQUNyRCxHQUFHLENBQUMsS0FBSyxDQUFDO0FBRVYsU0FBTztBQUNUOyIsCiAgIm5hbWVzIjogW10KfQo=
