export declare function ConfirmDialog({ cancelLabel, confirmLabel, description, destructive, loading, onCancel, onConfirm, open, title }: ConfirmDialogProps): import("react").JSX.Element;
interface ConfirmDialogProps {
    cancelLabel?: string;
    confirmLabel?: string;
    description?: string;
    destructive?: boolean;
    loading?: boolean;
    onCancel: () => void;
    onConfirm: () => void;
    open: boolean;
    title: string;
}
export {};
