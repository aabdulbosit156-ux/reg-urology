import { LogOut01 } from "@untitledui/icons";
import { Avatar } from "@/components/base/avatar/avatar";
import { useAuth } from "@/providers/auth-provider";

const ROLE_LABELS: Record<string, string> = {
    dev: "Dev",
    director: "Direktor",
    admin: "Admin",
    analyst: "Analizchi mutaxassis",
};

function getInitials(name: string): string {
    return name
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase() ?? "")
        .join("");
}

export const AccountFooter = () => {
    const { me, logout } = useAuth();
    if (!me) return null;

    const displayName = me.full_name ?? "Foydalanuvchi";

    return (
        <div className="flex items-center gap-3 rounded-xl p-3 ring-1 ring-secondary ring-inset">
            <Avatar size="md" initials={getInitials(displayName)} alt={displayName} />
            <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-primary">{displayName}</p>
                <p className="truncate text-xs text-tertiary">{ROLE_LABELS[me.role] ?? me.role}</p>
            </div>
            <button
                type="button"
                onClick={logout}
                aria-label="Chiqish"
                className="flex shrink-0 cursor-pointer items-center justify-center rounded-md p-1.5 text-fg-quaternary outline-focus-ring transition duration-100 ease-linear hover:bg-primary_hover hover:text-fg-quaternary_hover focus-visible:outline-2 focus-visible:outline-offset-2"
            >
                <LogOut01 className="size-4" />
            </button>
        </div>
    );
};
