import type { PropsWithChildren } from "react";
import { Navigate } from "react-router";
import { useAuth } from "@/providers/auth-provider";

const FullScreenLoader = () => (
    <div className="flex min-h-screen items-center justify-center bg-primary text-sm text-tertiary">
        Yuklanmoqda...
    </div>
);

export const RequireAuth = ({ children }: PropsWithChildren) => {
    const { me, isLoading } = useAuth();
    if (isLoading) return <FullScreenLoader />;
    if (!me) return <Navigate to="/login" replace />;
    return children;
};

export const RedirectIfAuthed = ({ children }: PropsWithChildren) => {
    const { me, isLoading } = useAuth();
    if (isLoading) return <FullScreenLoader />;
    if (me) return <Navigate to="/patients" replace />;
    return children;
};
