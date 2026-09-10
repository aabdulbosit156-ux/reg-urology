import { Activity, BarChartSquare02, Calendar, Settings01, Users01, Users03 } from "@untitledui/icons";
import { Outlet, useLocation } from "react-router";
import type { NavItemType } from "@/components/application/app-navigation/config";
import { SidebarNavigationSimple } from "@/components/application/app-navigation/sidebar-navigation/sidebar-simple";
import { AccountFooter } from "@/components/layout/account-footer";
import { MobileBottomNav } from "@/components/layout/mobile-bottom-nav";
import { MobileTopBar } from "@/components/layout/mobile-top-bar";
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

    // Faoliyat is a desktop admin task — leave it out of the mobile bottom bar so it doesn't crowd out the rest.
    const mobileNavItems = navItems.filter((item) => item.label !== "Faoliyat");

    return (
        <div className="flex h-dvh flex-col bg-secondary lg:h-screen lg:flex-row">
            <SidebarNavigationSimple
                activeUrl={location.pathname}
                items={navItems}
                showAccountCard={false}
                featureCard={<AccountFooter />}
                mobileHeader={<MobileTopBar />}
            />
            <main className="flex w-full flex-1 flex-col overflow-y-auto lg:px-8 lg:py-8">
                <Outlet />
            </main>
            <MobileBottomNav activeUrl={location.pathname} items={mobileNavItems} />
        </div>
    );
};
