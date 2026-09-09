export interface ScheduleSettings {
    work_start: string;
    work_end: string;
    slot_minutes: number;
}

export interface AISettings {
    ai_token_configured: boolean;
}

export interface BotSettings {
    bot_token_configured: boolean;
    bot_username: string | null;
}

export interface BotTexts {
    texts: Record<string, string>;
}

export interface ClinicProfile {
    clinic_name: string | null;
    clinic_lat: number | null;
    clinic_lng: number | null;
    clinic_contacts: Record<string, string>;
}
