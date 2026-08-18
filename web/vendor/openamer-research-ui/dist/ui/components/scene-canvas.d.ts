export declare function SceneCanvas({ camera, children, className, contained, frameloop, noEvents, style }: SceneCanvasProps): import("react").JSX.Element;
interface SceneCanvasProps {
    camera?: {
        far?: number;
        near?: number;
        position?: [number, number, number];
        zoom?: number;
    };
    children: () => React.ReactNode;
    className?: string;
    contained?: boolean;
    /**
     * R3F frame-loop mode. Defaults to `'always'` for backwards
     * compatibility, but `'demand'` is strongly preferred for static
     * scenes (use `invalidate()` from `useThree` to request frames). The
     * canvas additionally pauses (forces `'never'`) while the document
     * is hidden, regardless of this setting.
     */
    frameloop?: 'always' | 'demand' | 'never';
    noEvents?: boolean;
    style?: React.CSSProperties;
}
export {};
