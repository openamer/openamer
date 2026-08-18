import { type LensPreset } from './lens';
export declare function Lens({ dark, initial }: LensProps): import("react").JSX.Element;
interface LensProps {
    dark?: boolean;
    /**
     * Exact preset to seed the internal Leva controls with. When omitted the
     * component falls back to `LENS_0` / `LENS_5I` based on `dark`. Pass the
     * actual preset from a host (e.g. Storybook toolbar) to guarantee the
     * first-paint colors match the selected lens without needing a followup
     * `applyLens` that can be lost in useSmoothControls' startup window.
     */
    initial?: LensPreset;
}
export {};
