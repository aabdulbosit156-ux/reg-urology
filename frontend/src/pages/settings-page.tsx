import { PageHeader } from "@/components/layout/page-header";
import { AiSettingsCard } from "@/components/settings/ai-settings-card";
import { BotSettingsCard } from "@/components/settings/bot-settings-card";
import { BotTextsCard } from "@/components/settings/bot-texts-card";
import { ClinicSettingsCard } from "@/components/settings/clinic-settings-card";
import { ScheduleSettingsCard } from "@/components/settings/schedule-settings-card";

export const SettingsPage = () => {
    return (
        <div className="flex flex-col gap-6 px-4 py-6 pb-24 lg:px-0 lg:py-0">
            <PageHeader>
                <div>
                    <h1 className="text-xl font-semibold text-primary">Sozlamalar</h1>
                    <p className="text-sm text-tertiary">Klinika, bot va AI sozlamalari</p>
                </div>
            </PageHeader>

            <ScheduleSettingsCard />
            <BotSettingsCard />
            <AiSettingsCard />
            <BotTextsCard />
            <ClinicSettingsCard />
        </div>
    );
};
