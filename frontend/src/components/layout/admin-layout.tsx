import { Users01 } from "@untitledui/icons";
import { Outlet, useLocation } from "react-router";
import type { NavItemType } from "@/components/application/app-navigation/config";
import { SidebarNavigationSimple } from "@/components/application/app-navigation/sidebar-navigation/sidebar-simple";
import { AccountFooter } from "@/components/layout/account-footer";

const NAV_ITEMS: NavItemType[] = [{ label: "Bemorlar", href: "/patients", icon: Users01 }];

export const AdminLayout = () => {
    const location = useLocation();

    return (
        <div className="flex min-h-screen bg-secondary">
            <SidebarNavigationSimple
                activeUrl={location.pathname}
                items={NAV_ITEMS}
                showAccountCard={false}
                featureCard={<AccountFooter />}
            />
            <main className="w-full flex-1 px-4 py-6 lg:px-8 lg:py-8">
                <Outlet />
            </main>
        </div>
    );
};
