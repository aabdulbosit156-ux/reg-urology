import type { HTMLAttributes } from "react";
import { cx } from "@/utils/cx";

export const AppLogo = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => {
    return (
        <div {...props} className={cx("flex items-center", className)}>
            <span className="text-lg leading-none font-bold tracking-tight text-primary">
                Reg<span className="text-brand-secondary">Urolog</span>
            </span>
        </div>
    );
};
