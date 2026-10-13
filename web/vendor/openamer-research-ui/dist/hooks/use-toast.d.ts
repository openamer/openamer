export declare function useToast(duration?: number): {
    showToast: (message: string, type: "error" | "success") => void;
    toast: {
        message: string;
        type: "error" | "success";
    } | null;
};
