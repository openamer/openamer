import { useControls } from 'leva';
import { type WritableAtom } from 'nanostores';
export declare function useSmoothControls<T extends Record<string, any>>(label: string, initialArgs: T, options?: UseSmoothControlsOptions, dependencies?: Parameters<typeof useControls>[3]): { [K in keyof T]: T[K] extends {
    value: infer V;
} ? V : never; };
export declare const getControlAtom: <T = any>(label: string, key: string) => undefined | WritableAtom<T>;
export declare const setControlValue: <T = any>(label: string, key: string, value: T, options?: {
    animate?: boolean;
    duration?: number;
}) => void;
type UseSmoothControlsOptions = Parameters<typeof useControls>[2] & {
    duration?: number;
    onRandomize?: () => void;
    onReset?: () => void;
};
export {};
