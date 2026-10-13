export declare function Legend({ children, className, label, sub, ...props }: LegendProps): import("react").JSX.Element;
interface LegendProps extends React.ComponentProps<'hgroup'> {
    label: React.ReactNode;
    sub?: React.ReactNode;
}
export {};
