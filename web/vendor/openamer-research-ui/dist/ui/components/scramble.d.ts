import type { RefObject } from 'react';
export declare function Scramble({ children, dur, spread, target }: ScrambleProps): import("react").JSX.Element;
interface ScrambleProps {
    children: string;
    dur?: number;
    spread?: number;
    target?: RefObject<HTMLElement | null>;
}
export {};
