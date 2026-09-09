import { Activity, BarChartSquare02, Calendar, Settings01, Users01, Users03 } from "@untitledui/icons";
import { Outlet, useLocation } from "react-router";
import type { NavItemType } from "@/components/application/app-navigation/config";
import { SidebarNavigationSimple } from "@/components/application/app-navigation/sidebar-navigation/sidebar-simple";
import { AccountFooter } from "@/components/layout/account-footer";
import { useAuth } from "@/providers/auth-provider";

export const AdminLayout = () => {
    const location = useLocation();
    const { me } = useAuth();

    const navItems: NavItemType[] = [{ label: "Dashboard", href: "/dashboard", icon: BarChartSquare02 }];
    navItems.push({ label: "Bemorlar", href: "/patients", icon: Users01 });
    if (me?.role !== "analyst") {
        navItems.push({ label: "Kalendar", href: "/calendar", icon: Calendar });
        navItems.push({ label: "Xodimlar", href: "/staff", icon: Users03 });
    }
    if (me?.role === "dev" || me?.role === "director") {
        navItems.push({ label: "Faoliyat", href: "/activity", icon: Activity });
        navItems.push({ label: "Sozlamalar", href: "/settings", icon: Settings01 });
    }

    return (
        <div className="flex min-h-screen bg-secondary">
            <SidebarNavigationSimple
                activeUrl={location.pathname}
                items={navItems}
                showAccountCard={false}
                featureCard={<AccountFooter />}
            />
            <main className="w-full flex-1 px-4 py-6 lg:px-8 lg:py-8">
                <Outlet />
            </main>
        </div>
    );
};
