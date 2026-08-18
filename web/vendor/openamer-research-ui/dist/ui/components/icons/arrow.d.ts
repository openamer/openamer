import type { SVGProps } from 'react';
export declare function ArrowIcon({ className, direction, ...props }: ArrowIconProps): import("react").JSX.Element;
interface ArrowIconProps extends SVGProps<SVGSVGElement> {
    direction?: 'down' | 'left' | 'right' | 'up';
}
export {};
