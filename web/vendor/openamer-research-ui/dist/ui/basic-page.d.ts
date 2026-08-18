import type { ReactNode } from 'react';
export declare function BasicPage({ children, subtitle, title }: BasicPageProps): import("react").JSX.Element;
interface BasicPageProps extends React.PropsWithChildren {
    subtitle?: string;
    title?: ReactNode;
}
export {};
