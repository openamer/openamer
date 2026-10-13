"use client";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { Glitch } from "./glitch.js";
import { Greys } from "./greys.js";
import { Lens } from "./lens-layers.js";
import { Noise } from "./noise.js";
import { Vignette } from "./vignette.js";
export { BLEND_MODES } from "./blend-modes.js";
export { Glitch } from "./glitch.js";
export { Greys } from "./greys.js";
export { Lens } from "./lens-layers.js";
export { Noise } from "./noise.js";
export { Vignette } from "./vignette.js";
export {
  $lightMode,
  applyLens,
  lens0,
  lens5i,
  LENS_0,
  LENS_5I,
  LENSES,
  toggleLens
} from "./lens";
const LAYER = "pointer-events-none fixed inset-0";
export function Overlays({ dark, initial }) {
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(Lens, { dark, initial }),
    /* @__PURE__ */ jsx(Noise, { className: LAYER, style: { zIndex: 101 } }),
    /* @__PURE__ */ jsx(Vignette, { className: LAYER, style: { zIndex: 99 } }),
    /* @__PURE__ */ jsx(Greys, { className: LAYER, style: { zIndex: 200 } }),
    /* @__PURE__ */ jsx(Glitch, { className: LAYER, style: { zIndex: 201 } })
  ] });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IEdsaXRjaCB9IGZyb20gJy4vZ2xpdGNoJ1xuaW1wb3J0IHsgR3JleXMgfSBmcm9tICcuL2dyZXlzJ1xuaW1wb3J0IHsgTGVucyB9IGZyb20gJy4vbGVucy1sYXllcnMnXG5pbXBvcnQgeyBOb2lzZSB9IGZyb20gJy4vbm9pc2UnXG5pbXBvcnQgeyBWaWduZXR0ZSB9IGZyb20gJy4vdmlnbmV0dGUnXG5cbmltcG9ydCB0eXBlIHsgTGVuc1ByZXNldCB9IGZyb20gJy4vbGVucydcblxuZXhwb3J0IHsgQkxFTkRfTU9ERVMgfSBmcm9tICcuL2JsZW5kLW1vZGVzJ1xuZXhwb3J0IHsgR2xpdGNoIH0gZnJvbSAnLi9nbGl0Y2gnXG5leHBvcnQgeyBHcmV5cyB9IGZyb20gJy4vZ3JleXMnXG5leHBvcnQgeyBMZW5zIH0gZnJvbSAnLi9sZW5zLWxheWVycydcbmV4cG9ydCB7IE5vaXNlIH0gZnJvbSAnLi9ub2lzZSdcbmV4cG9ydCB7IFZpZ25ldHRlIH0gZnJvbSAnLi92aWduZXR0ZSdcbmV4cG9ydCB7XG4gICRsaWdodE1vZGUsXG4gIGFwcGx5TGVucyxcbiAgbGVuczAsXG4gIGxlbnM1aSxcbiAgTEVOU18wLFxuICBMRU5TXzVJLFxuICBMRU5TRVMsXG4gIHRvZ2dsZUxlbnNcbn0gZnJvbSAnLi9sZW5zJ1xuZXhwb3J0IHR5cGUgeyBMZW5zUHJlc2V0IH0gZnJvbSAnLi9sZW5zJ1xuXG5jb25zdCBMQVlFUiA9ICdwb2ludGVyLWV2ZW50cy1ub25lIGZpeGVkIGluc2V0LTAnXG5cbmV4cG9ydCBmdW5jdGlvbiBPdmVybGF5cyh7IGRhcmssIGluaXRpYWwgfTogT3ZlcmxheXNQcm9wcykge1xuICByZXR1cm4gKFxuICAgIDw+XG4gICAgICA8TGVucyBkYXJrPXtkYXJrfSBpbml0aWFsPXtpbml0aWFsfSAvPlxuXG4gICAgICA8Tm9pc2UgY2xhc3NOYW1lPXtMQVlFUn0gc3R5bGU9e3sgekluZGV4OiAxMDEgfX0gLz5cbiAgICAgIDxWaWduZXR0ZSBjbGFzc05hbWU9e0xBWUVSfSBzdHlsZT17eyB6SW5kZXg6IDk5IH19IC8+XG4gICAgICA8R3JleXMgY2xhc3NOYW1lPXtMQVlFUn0gc3R5bGU9e3sgekluZGV4OiAyMDAgfX0gLz5cbiAgICAgIDxHbGl0Y2ggY2xhc3NOYW1lPXtMQVlFUn0gc3R5bGU9e3sgekluZGV4OiAyMDEgfX0gLz5cbiAgICA8Lz5cbiAgKVxufVxuXG5pbnRlcmZhY2UgT3ZlcmxheXNQcm9wcyB7XG4gIGRhcms/OiBib29sZWFuXG4gIGluaXRpYWw/OiBMZW5zUHJlc2V0XG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBZ0NJLG1CQUNFLEtBREY7QUE5QkosU0FBUyxjQUFjO0FBQ3ZCLFNBQVMsYUFBYTtBQUN0QixTQUFTLFlBQVk7QUFDckIsU0FBUyxhQUFhO0FBQ3RCLFNBQVMsZ0JBQWdCO0FBSXpCLFNBQVMsbUJBQW1CO0FBQzVCLFNBQVMsY0FBYztBQUN2QixTQUFTLGFBQWE7QUFDdEIsU0FBUyxZQUFZO0FBQ3JCLFNBQVMsYUFBYTtBQUN0QixTQUFTLGdCQUFnQjtBQUN6QjtBQUFBLEVBQ0U7QUFBQSxFQUNBO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFBQSxFQUNBO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFBQSxFQUNBO0FBQUEsT0FDSztBQUdQLE1BQU0sUUFBUTtBQUVQLGdCQUFTLFNBQVMsRUFBRSxNQUFNLFFBQVEsR0FBa0I7QUFDekQsU0FDRSxpQ0FDRTtBQUFBLHdCQUFDLFFBQUssTUFBWSxTQUFrQjtBQUFBLElBRXBDLG9CQUFDLFNBQU0sV0FBVyxPQUFPLE9BQU8sRUFBRSxRQUFRLElBQUksR0FBRztBQUFBLElBQ2pELG9CQUFDLFlBQVMsV0FBVyxPQUFPLE9BQU8sRUFBRSxRQUFRLEdBQUcsR0FBRztBQUFBLElBQ25ELG9CQUFDLFNBQU0sV0FBVyxPQUFPLE9BQU8sRUFBRSxRQUFRLElBQUksR0FBRztBQUFBLElBQ2pELG9CQUFDLFVBQU8sV0FBVyxPQUFPLE9BQU8sRUFBRSxRQUFRLElBQUksR0FBRztBQUFBLEtBQ3BEO0FBRUo7IiwKICAibmFtZXMiOiBbXQp9Cg==
