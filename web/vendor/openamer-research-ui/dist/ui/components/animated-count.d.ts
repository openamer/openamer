export declare function useAnimatedCount(from: number, rate: number, ts?: Date, pausedAt?: Date): number;
export declare function AnimatedCount({ damping, duration, pausedAt, rate, value }: Props): import("react").JSX.Element;
interface Props {
    damping?: number;
    duration?: number;
    pausedAt?: Date;
    rate?: number;
    value: number;
}
export {};
