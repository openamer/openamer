import { type SocialLink } from './components/socials';
export declare function Footer({ className, groups, LinkComponent, socials, socialsLabel, style, themeLabel, themeToggle }: FooterProps): import("react").JSX.Element;
export interface FooterGroup {
    label: string;
    links: (FooterLink | string)[];
}
export interface FooterLink {
    href: string;
    label: string;
}
export interface FooterProps {
    className?: string;
    groups?: FooterGroup[];
    LinkComponent?: React.ElementType;
    socials?: SocialLink[];
    socialsLabel?: string;
    style?: React.CSSProperties;
    themeLabel?: string;
    themeToggle?: boolean;
}
