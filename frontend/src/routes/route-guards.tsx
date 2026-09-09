import type { PropsWithChildren } from "react";
import { Navigate } from "react-router";
import { useAuth, type StaffRole } from "@/providers/auth-provider";

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
    if (me) return <Navigate to="/dashboard" replace />;
    return children;
};

export const RequireRole = ({ roles, children }: PropsWithChildren<{ roles: StaffRole[] }>) => {
    const { me, isLoading } = useAuth();
    if (isLoading) return <FullScreenLoader />;
    if (!me) return <Navigate to="/login" replace />;
    if (!roles.includes(me.role)) return <Navigate to="/patients" replace />;
    return children;
};
