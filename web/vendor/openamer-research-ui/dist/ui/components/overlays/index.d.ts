import type { LensPreset } from './lens';
export { BLEND_MODES } from './blend-modes';
export { Glitch } from './glitch';
export { Greys } from './greys';
export { Lens } from './lens-layers';
export { Noise } from './noise';
export { Vignette } from './vignette';
export { $lightMode, applyLens, lens0, lens5i, LENS_0, LENS_5I, LENSES, toggleLens } from './lens';
export type { LensPreset } from './lens';
export declare function Overlays({ dark, initial }: OverlaysProps): import("react").JSX.Element;
interface OverlaysProps {
    dark?: boolean;
    initial?: LensPreset;
}
