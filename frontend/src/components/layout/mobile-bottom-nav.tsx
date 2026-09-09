import { Link as AriaLink } from "react-aria-components";
import type { NavItemType } from "@/components/application/app-navigation/config";
import { cx } from "@/utils/cx";

interface MobileBottomNavProps {
    items: NavItemType[];
    activeUrl?: string;
}

export const MobileBottomNav = ({ items, activeUrl }: MobileBottomNavProps) => {
    return (
        <nav
            className="fixed inset-x-0 bottom-0 z-40 flex gap-1 overflow-x-auto border-t border-secondary bg-primary px-2 py-2 lg:hidden"
            style={{ paddingBottom: "calc(0.5rem + env(safe-area-inset-bottom))" }}
        >
            {items.map((item) => {
                const isActive = item.href === activeUrl;
                const Icon = item.icon;
                return (
                    <AriaLink
                        key={item.href}
                        href={item.href}
                        className={cx(
                            "flex min-w-16 shrink-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-2xl px-2 py-1.5 text-xs font-medium outline-focus-ring transition duration-100 ease-linear",
                            isActive
                                ? "bg-brand-primary_alt text-brand-secondary"
                                : "text-tertiary hover:bg-primary_hover hover:text-secondary",
                        )}
                    >
                        {Icon && <Icon className="size-5" />}
                        <span className="truncate">{item.label}</span>
                    </AriaLink>
                );
            })}
        </nav>
    );
};
