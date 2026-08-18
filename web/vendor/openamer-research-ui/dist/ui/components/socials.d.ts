export declare function Socials({ className, items, onNavigate, ...rest }: SocialsProps): import("react").JSX.Element;
export interface SocialLink {
    external?: boolean;
    href: string;
    icon: React.ComponentType<{
        className?: string;
    }>;
    label: string;
    onClick?: React.MouseEventHandler;
}
interface SocialsProps extends React.HTMLAttributes<HTMLDivElement> {
    items: SocialLink[];
    /**
     * Called *in addition* to each link's `onClick` after a click — useful in
     * mobile drawer / dialog contexts where clicking a link should also close
     * the surrounding overlay.
     */
    onNavigate?: () => void;
}
export {};
