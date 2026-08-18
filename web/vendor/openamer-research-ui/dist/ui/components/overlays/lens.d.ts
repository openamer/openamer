export declare const LENS_0: {
    Globe: {
        innerColor: string;
        innerOpacity: number;
        outerColor: string;
    };
    Lens: {
        bgBlend: string;
        bgColor: string;
        bgOpacity: number;
        fgColor: string;
        fgOpacity: number;
        fillerOpacity: number;
        mgColor: string;
        mgOpacity: number;
    };
};
export declare const LENS_5I: {
    Globe: {
        innerColor: string;
        innerOpacity: number;
        outerColor: string;
    };
    Lens: {
        bgBlend: string;
        bgColor: string;
        bgOpacity: number;
        fgColor: string;
        fgOpacity: number;
        fillerOpacity: number;
        mgColor: string;
        mgOpacity: number;
    };
};
export declare const lens0: (l?: Partial<typeof LENS_0.Lens>, g?: Partial<typeof LENS_0.Globe>) => LensPreset;
export declare const lens5i: (l?: Partial<typeof LENS_5I.Lens>, g?: Partial<typeof LENS_5I.Globe>) => LensPreset;
export declare const LENSES: [string, LensPreset][];
export declare const applyLens: (preset: LensPreset, animate?: boolean) => void;
export declare const $lightMode: import("nanostores").PreinitializedWritableAtom<boolean> & object;
export declare const toggleLens: () => void;
export interface LensPreset {
    Globe: typeof LENS_0.Globe;
    Lens: typeof LENS_0.Lens;
}
