import { LogOut01 } from "@untitledui/icons";
import {
    Button as AriaButton,
    Dialog as AriaDialog,
    DialogTrigger as AriaDialogTrigger,
    Popover as AriaPopover,
} from "react-aria-components";
import { Avatar } from "@/components/base/avatar/avatar";
import { ROLE_LABELS } from "@/lib/staff-role";
import { useAuth } from "@/providers/auth-provider";
import { cx } from "@/utils/cx";

function getInitials(name: string): string {
    return name
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase() ?? "")
        .join("");
}

export const MobileProfileMenu = () => {
    const { me, logout } = useAuth();
    if (!me) return null;

    const displayName = me.full_name ?? "Foydalanuvchi";
    const roleLabel = ROLE_LABELS[me.role] ?? me.role;

    return (
        <AriaDialogTrigger>
            <AriaButton aria-label="Profil" className="cursor-pointer rounded-full outline-focus-ring focus-visible:outline-2">
                <Avatar size="sm" initials={getInitials(displayName)} alt={displayName} />
            </AriaButton>
            <AriaPopover
                placement="bottom right"
                offset={8}
                className={({ isEntering, isExiting }) =>
                    cx(
                        "origin-(--trigger-anchor-point) will-change-transform",
                        isEntering && "duration-150 ease-out animate-in fade-in",
                        isExiting && "duration-100 ease-in animate-out fade-out",
                    )
                }
            >
                <AriaDialog className="w-56 rounded-xl bg-primary p-1.5 shadow-lg ring-1 ring-secondary outline-hidden">
                    <div className="flex items-center gap-3 p-2">
                        <Avatar size="md" initials={getInitials(displayName)} alt={displayName} />
                        <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-primary">{displayName}</p>
                            <p className="truncate text-xs text-tertiary">{roleLabel}</p>
                        </div>
                    </div>
                    <div className="border-t border-secondary pt-1">
                        <button
                            type="button"
                            onClick={logout}
                            className="flex w-full cursor-pointer items-center gap-2 rounded-md p-2 text-left text-sm font-medium text-secondary outline-focus-ring transition duration-100 ease-linear hover:bg-primary_hover"
                        >
                            <LogOut01 className="size-4 text-fg-quaternary" />
                            Chiqish
                        </button>
                    </div>
                </AriaDialog>
            </AriaPopover>
        </AriaDialogTrigger>
    );
};
