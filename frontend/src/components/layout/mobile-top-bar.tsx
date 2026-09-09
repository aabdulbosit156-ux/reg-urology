import { AppLogo } from "@/components/foundations/logo/app-logo";
import { MobileProfileMenu } from "@/components/layout/mobile-profile-menu";

export const MobileTopBar = () => {
    return (
        <header className="flex h-14 items-center justify-between border-b border-secondary bg-primary p-3 pl-4 lg:hidden">
            <AppLogo className="h-6" />
            <MobileProfileMenu />
        </header>
    );
};
