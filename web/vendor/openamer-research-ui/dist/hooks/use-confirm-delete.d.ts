export declare function useConfirmDelete<TId>({ onDelete }: {
    onDelete: (id: TId) => Promise<void>;
}): {
    readonly cancel: () => void;
    readonly confirm: () => Promise<void>;
    readonly isDeleting: boolean;
    readonly isOpen: boolean;
    readonly pendingId: TId | null;
    readonly requestDelete: (id: TId) => void;
};
