import { AiSettingsCard } from "@/components/settings/ai-settings-card";
import { BotSettingsCard } from "@/components/settings/bot-settings-card";
import { BotTextsCard } from "@/components/settings/bot-texts-card";
import { ClinicSettingsCard } from "@/components/settings/clinic-settings-card";
import { ScheduleSettingsCard } from "@/components/settings/schedule-settings-card";

export const SettingsPage = () => {
    return (
        <div className="flex flex-col gap-6">
            <div>
                <h1 className="text-xl font-semibold text-primary">Sozlamalar</h1>
                <p className="text-sm text-tertiary">Klinika, bot va AI sozlamalari</p>
            </div>

            <ScheduleSettingsCard />
            <BotSettingsCard />
            <AiSettingsCard />
            <BotTextsCard />
            <ClinicSettingsCard />
        </div>
    );
};
