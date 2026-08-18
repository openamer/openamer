import { type ReactNode } from 'react';
/**
 * Mobile-first bottom sheet with slide + fade enter/exit, drag-to-dismiss
 * handle, body scroll lock, and reduced-motion support. Portaled to
 * `document.body` to escape ancestor stacking contexts.
 */
export declare function BottomSheet({ backdropDismissLabel, children, onClose, open, title }: BottomSheetProps): import("react").ReactPortal | null;
interface BottomSheetProps {
    backdropDismissLabel?: string;
    children: ReactNode;
    onClose: () => void;
    open: boolean;
    title: string;
}
export {};
