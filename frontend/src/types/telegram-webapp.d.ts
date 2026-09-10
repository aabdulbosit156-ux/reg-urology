import type { TelegramLoginData } from "@/providers/auth-provider";

export {};

declare global {
    interface Window {
        Telegram?: {
            WebApp?: {
                initData: string;
                ready: () => void;
                expand: () => void;
            };
        };
        onTelegramAuth?: (user: TelegramLoginData) => void;
    }
}
