import type { ReactNode } from "react";
import { cx } from "@/utils/cx";

interface PageHeaderProps {
    children: ReactNode;
    className?: string;
}

/** Sticks the page's title/controls to the top of the scrollable content area on mobile. */
export const PageHeader = ({ children, className }: PageHeaderProps) => (
    <div
        className={cx(
            "sticky top-0 z-10 -mx-4 -mt-6 flex flex-col gap-4 bg-secondary px-4 pt-6 pb-4",
            "lg:static lg:z-auto lg:mx-0 lg:mt-0 lg:bg-transparent lg:px-0 lg:pt-0 lg:pb-0",
            className,
        )}
    >
        {children}
    </div>
);
