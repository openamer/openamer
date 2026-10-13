import { clsx } from "clsx";
import sanitize from "sanitize-html";
import { twMerge } from "tailwind-merge";
import * as THREE from "three";
import { hexToRgb, rgbToHex } from "./color.js";
import { polyRef } from "./poly.js";
export { hexToRgb, polyRef, rgbToHex };
export const cn = (...inputs) => twMerge(clsx(inputs));
export const clamp = (v, min = 0, max = 1) => Math.min(max, Math.max(min, Number.isFinite(v) ? v : min));
export const smoothstep = (edge0, edge1, x) => {
  const t = clamp((x - edge0) / (edge1 - edge0));
  return t * t * (3 - 2 * t);
};
export const hexToVec3 = (hex) => {
  const [r, g, b] = hexToRgb(hex);
  return new THREE.Vector3(r / 255, g / 255, b / 255);
};
export const truncate = (text, options) => text.length > options.length ? `${text.slice(0, options.length)}...` : text;
export const stripWpStyles = (html) => sanitize(html, {
  allowedAttributes: {
    a: ["href", "target", "rel", "name"],
    audio: ["src", "controls"],
    iframe: ["src", "width", "height", "frameborder", "allowfullscreen"],
    img: ["src", "alt", "width", "height", "loading"],
    source: ["src", "type", "srcset"],
    td: ["colspan", "rowspan"],
    th: ["colspan", "rowspan"],
    video: ["src", "controls", "width", "height", "poster"]
  },
  allowedIframeHostnames: [
    "www.youtube.com",
    "youtube.com",
    "player.vimeo.com"
  ],
  allowedSchemes: ["http", "https", "mailto"],
  allowedTags: [
    ...sanitize.defaults.allowedTags,
    "img",
    "figure",
    "figcaption",
    "iframe",
    "video",
    "audio",
    "source",
    "picture"
  ]
});
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgdHlwZSBDbGFzc1ZhbHVlLCBjbHN4IH0gZnJvbSAnY2xzeCdcbmltcG9ydCBzYW5pdGl6ZSBmcm9tICdzYW5pdGl6ZS1odG1sJ1xuaW1wb3J0IHsgdHdNZXJnZSB9IGZyb20gJ3RhaWx3aW5kLW1lcmdlJ1xuaW1wb3J0ICogYXMgVEhSRUUgZnJvbSAndGhyZWUnXG5cbmltcG9ydCB7IGhleFRvUmdiLCByZ2JUb0hleCB9IGZyb20gJy4vY29sb3InXG5pbXBvcnQgeyBwb2x5UmVmIH0gZnJvbSAnLi9wb2x5J1xuaW1wb3J0IHR5cGUgeyBQb2x5Q29tcG9uZW50LCBQb2x5UHJvcHMsIFBvbHlSZWYgfSBmcm9tICcuL3BvbHknXG5cbmV4cG9ydCB7IGhleFRvUmdiLCBwb2x5UmVmLCByZ2JUb0hleCB9XG5leHBvcnQgdHlwZSB7IFBvbHlDb21wb25lbnQsIFBvbHlQcm9wcywgUG9seVJlZiB9XG5cbmV4cG9ydCBjb25zdCBjbiA9ICguLi5pbnB1dHM6IENsYXNzVmFsdWVbXSkgPT4gdHdNZXJnZShjbHN4KGlucHV0cykpXG5cbmV4cG9ydCBjb25zdCBjbGFtcCA9ICh2OiBudW1iZXIsIG1pbiA9IDAsIG1heCA9IDEpID0+XG4gIE1hdGgubWluKG1heCwgTWF0aC5tYXgobWluLCBOdW1iZXIuaXNGaW5pdGUodikgPyB2IDogbWluKSlcblxuZXhwb3J0IGNvbnN0IHNtb290aHN0ZXAgPSAoZWRnZTA6IG51bWJlciwgZWRnZTE6IG51bWJlciwgeDogbnVtYmVyKSA9PiB7XG4gIGNvbnN0IHQgPSBjbGFtcCgoeCAtIGVkZ2UwKSAvIChlZGdlMSAtIGVkZ2UwKSlcblxuICByZXR1cm4gdCAqIHQgKiAoMyAtIDIgKiB0KVxufVxuXG5leHBvcnQgY29uc3QgaGV4VG9WZWMzID0gKGhleDogc3RyaW5nKSA9PiB7XG4gIGNvbnN0IFtyLCBnLCBiXSA9IGhleFRvUmdiKGhleClcblxuICByZXR1cm4gbmV3IFRIUkVFLlZlY3RvcjMociAvIDI1NSwgZyAvIDI1NSwgYiAvIDI1NSlcbn1cblxuZXhwb3J0IGNvbnN0IHRydW5jYXRlID0gKHRleHQ6IHN0cmluZywgb3B0aW9uczogeyBsZW5ndGg6IG51bWJlciB9KSA9PlxuICB0ZXh0Lmxlbmd0aCA+IG9wdGlvbnMubGVuZ3RoID8gYCR7dGV4dC5zbGljZSgwLCBvcHRpb25zLmxlbmd0aCl9Li4uYCA6IHRleHRcblxuZXhwb3J0IGNvbnN0IHN0cmlwV3BTdHlsZXMgPSAoaHRtbDogc3RyaW5nKSA9PlxuICBzYW5pdGl6ZShodG1sLCB7XG4gICAgYWxsb3dlZEF0dHJpYnV0ZXM6IHtcbiAgICAgIGE6IFsnaHJlZicsICd0YXJnZXQnLCAncmVsJywgJ25hbWUnXSxcbiAgICAgIGF1ZGlvOiBbJ3NyYycsICdjb250cm9scyddLFxuICAgICAgaWZyYW1lOiBbJ3NyYycsICd3aWR0aCcsICdoZWlnaHQnLCAnZnJhbWVib3JkZXInLCAnYWxsb3dmdWxsc2NyZWVuJ10sXG4gICAgICBpbWc6IFsnc3JjJywgJ2FsdCcsICd3aWR0aCcsICdoZWlnaHQnLCAnbG9hZGluZyddLFxuICAgICAgc291cmNlOiBbJ3NyYycsICd0eXBlJywgJ3NyY3NldCddLFxuICAgICAgdGQ6IFsnY29sc3BhbicsICdyb3dzcGFuJ10sXG4gICAgICB0aDogWydjb2xzcGFuJywgJ3Jvd3NwYW4nXSxcbiAgICAgIHZpZGVvOiBbJ3NyYycsICdjb250cm9scycsICd3aWR0aCcsICdoZWlnaHQnLCAncG9zdGVyJ11cbiAgICB9LFxuICAgIGFsbG93ZWRJZnJhbWVIb3N0bmFtZXM6IFtcbiAgICAgICd3d3cueW91dHViZS5jb20nLFxuICAgICAgJ3lvdXR1YmUuY29tJyxcbiAgICAgICdwbGF5ZXIudmltZW8uY29tJ1xuICAgIF0sXG4gICAgYWxsb3dlZFNjaGVtZXM6IFsnaHR0cCcsICdodHRwcycsICdtYWlsdG8nXSxcbiAgICBhbGxvd2VkVGFnczogW1xuICAgICAgLi4uc2FuaXRpemUuZGVmYXVsdHMuYWxsb3dlZFRhZ3MsXG4gICAgICAnaW1nJyxcbiAgICAgICdmaWd1cmUnLFxuICAgICAgJ2ZpZ2NhcHRpb24nLFxuICAgICAgJ2lmcmFtZScsXG4gICAgICAndmlkZW8nLFxuICAgICAgJ2F1ZGlvJyxcbiAgICAgICdzb3VyY2UnLFxuICAgICAgJ3BpY3R1cmUnXG4gICAgXVxuICB9KVxuIl0sCiAgIm1hcHBpbmdzIjogIkFBQUEsU0FBMEIsWUFBWTtBQUN0QyxPQUFPLGNBQWM7QUFDckIsU0FBUyxlQUFlO0FBQ3hCLFlBQVksV0FBVztBQUV2QixTQUFTLFVBQVUsZ0JBQWdCO0FBQ25DLFNBQVMsZUFBZTtBQUd4QixTQUFTLFVBQVUsU0FBUztBQUdyQixhQUFNLEtBQUssSUFBSSxXQUF5QixRQUFRLEtBQUssTUFBTSxDQUFDO0FBRTVELGFBQU0sUUFBUSxDQUFDLEdBQVcsTUFBTSxHQUFHLE1BQU0sTUFDOUMsS0FBSyxJQUFJLEtBQUssS0FBSyxJQUFJLEtBQUssT0FBTyxTQUFTLENBQUMsSUFBSSxJQUFJLEdBQUcsQ0FBQztBQUVwRCxhQUFNLGFBQWEsQ0FBQyxPQUFlLE9BQWUsTUFBYztBQUNyRSxRQUFNLElBQUksT0FBTyxJQUFJLFVBQVUsUUFBUSxNQUFNO0FBRTdDLFNBQU8sSUFBSSxLQUFLLElBQUksSUFBSTtBQUMxQjtBQUVPLGFBQU0sWUFBWSxDQUFDLFFBQWdCO0FBQ3hDLFFBQU0sQ0FBQyxHQUFHLEdBQUcsQ0FBQyxJQUFJLFNBQVMsR0FBRztBQUU5QixTQUFPLElBQUksTUFBTSxRQUFRLElBQUksS0FBSyxJQUFJLEtBQUssSUFBSSxHQUFHO0FBQ3BEO0FBRU8sYUFBTSxXQUFXLENBQUMsTUFBYyxZQUNyQyxLQUFLLFNBQVMsUUFBUSxTQUFTLEdBQUcsS0FBSyxNQUFNLEdBQUcsUUFBUSxNQUFNLENBQUMsUUFBUTtBQUVsRSxhQUFNLGdCQUFnQixDQUFDLFNBQzVCLFNBQVMsTUFBTTtBQUFBLEVBQ2IsbUJBQW1CO0FBQUEsSUFDakIsR0FBRyxDQUFDLFFBQVEsVUFBVSxPQUFPLE1BQU07QUFBQSxJQUNuQyxPQUFPLENBQUMsT0FBTyxVQUFVO0FBQUEsSUFDekIsUUFBUSxDQUFDLE9BQU8sU0FBUyxVQUFVLGVBQWUsaUJBQWlCO0FBQUEsSUFDbkUsS0FBSyxDQUFDLE9BQU8sT0FBTyxTQUFTLFVBQVUsU0FBUztBQUFBLElBQ2hELFFBQVEsQ0FBQyxPQUFPLFFBQVEsUUFBUTtBQUFBLElBQ2hDLElBQUksQ0FBQyxXQUFXLFNBQVM7QUFBQSxJQUN6QixJQUFJLENBQUMsV0FBVyxTQUFTO0FBQUEsSUFDekIsT0FBTyxDQUFDLE9BQU8sWUFBWSxTQUFTLFVBQVUsUUFBUTtBQUFBLEVBQ3hEO0FBQUEsRUFDQSx3QkFBd0I7QUFBQSxJQUN0QjtBQUFBLElBQ0E7QUFBQSxJQUNBO0FBQUEsRUFDRjtBQUFBLEVBQ0EsZ0JBQWdCLENBQUMsUUFBUSxTQUFTLFFBQVE7QUFBQSxFQUMxQyxhQUFhO0FBQUEsSUFDWCxHQUFHLFNBQVMsU0FBUztBQUFBLElBQ3JCO0FBQUEsSUFDQTtBQUFBLElBQ0E7QUFBQSxJQUNBO0FBQUEsSUFDQTtBQUFBLElBQ0E7QUFBQSxJQUNBO0FBQUEsSUFDQTtBQUFBLEVBQ0Y7QUFDRixDQUFDOyIsCiAgIm5hbWVzIjogW10KfQo=
