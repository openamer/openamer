import { type SocialLink } from './components/socials';
export declare function Header({ brand, brandHref, className, desktopGridStyle, links, LinkComponent, scramble: scrambleProp, socials, socialsLabel, style, themeLabel, themeToggle }: HeaderProps): import("react").JSX.Element;
export interface HeaderLink {
    external?: boolean;
    href: string;
    label: string;
    onClick?: React.MouseEventHandler;
}
export interface HeaderProps {
    brand?: React.ReactNode;
    brandHref?: string;
    className?: string;
    /**
     * Inline `style` for the desktop `Grid` only — useful for overriding
     * `grid-template-columns` (e.g. to align with a sidebar track) without
     * affecting the mobile bar or drawer.
     */
    desktopGridStyle?: React.CSSProperties;
    links?: HeaderLink[];
    LinkComponent?: React.ElementType;
    /**
     * Apply the hover-Scramble effect to nav link labels. Defaults to `true`,
     * automatically suppressed on tier-0 GPUs and when the user has
     * `prefers-reduced-motion: reduce`.
     */
    scramble?: boolean;
    /**
     * Optional socials shown in a trailing chrome cell on desktop and in the
     * mobile drawer's chrome row. For nav-heavy products (≥ 5 links) prefer
     * passing socials to `<Footer>` instead — the desktop `Grid` only ships
     * column rules through `grid-cols-6`, so brand + many links + chrome can
     * overflow.
     */
    socials?: SocialLink[];
    socialsLabel?: string;
    style?: React.CSSProperties;
    themeLabel?: string;
    themeToggle?: boolean;
}
/** @deprecated Use `SocialLink` from `@openamer-research/ui`. Same shape. */
export type HeaderSocial = SocialLink;
