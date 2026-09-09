import { useCallback, useEffect, useState } from "react";
import { Check, Stars02, UploadCloud02 } from "@untitledui/icons";
import { useNavigate } from "react-router";
import { SlideoutMenu } from "@/components/application/slideout-menus/slideout-menu";
import { Button } from "@/components/base/buttons/button";
import { TextArea } from "@/components/base/textarea/textarea";
import { StatusBadge } from "@/components/patients/status-badge";
import { STATUS_LABELS, STATUS_ORDER, VALID_TRANSITIONS } from "@/lib/patient-status";
import { ApiError, api, fetchBlob } from "@/lib/api-client";
import { useAuth } from "@/providers/auth-provider";
import { cx } from "@/utils/cx";
import type { PatientDetail, PatientStatus } from "@/types/patient";

function formatDateTime(iso: string): string {
    return new Date(iso).toLocaleString("uz-UZ", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

interface PatientSlideoutProps {
    patientId: string | null;
    onOpenChange: (open: boolean) => void;
    onChanged: () => void;
}

export const PatientSlideout = ({ patientId, onOpenChange, onChanged }: PatientSlideoutProps) => {
    const { me } = useAuth();
    const navigate = useNavigate();
    const canManageStatus = me?.role !== "analyst";

    const [patient, setPatient] = useState<PatientDetail | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);

    const [pendingStatus, setPendingStatus] = useState<PatientStatus | null>(null);
    const [note, setNote] = useState("");
    const [statusError, setStatusError] = useState<string | null>(null);
    const [isSubmittingStatus, setIsSubmittingStatus] = useState(false);

    const [uploadFile, setUploadFile] = useState<File | null>(null);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [isUploading, setIsUploading] = useState(false);

    const [aiLoadingId, setAiLoadingId] = useState<string | null>(null);
    const [aiError, setAiError] = useState<string | null>(null);

    const loadPatient = useCallback(async () => {
        if (!patientId) return;
        setIsLoading(true);
        setLoadError(null);
        try {
            const detail = await api.get<PatientDetail>(`/patients/${patientId}`);
            setPatient(detail);
        } catch (err) {
            setLoadError(err instanceof ApiError ? err.message : "Yuklashda xatolik");
        } finally {
            setIsLoading(false);
        }
    }, [patientId]);

    useEffect(() => {
        if (patientId) {
            loadPatient();
        } else {
            setPatient(null);
            setPendingStatus(null);
            setNote("");
            setStatusError(null);
            setUploadFile(null);
            setUploadError(null);
        }
    }, [patientId, loadPatient]);

    const handleConfirmStatus = async () => {
        if (!pendingStatus || !patient) return;
        setStatusError(null);
        setIsSubmittingStatus(true);
        try {
            await api.patch(`/patients/${patient.id}/status`, { to_status: pendingStatus, note: note || null });
            setPendingStatus(null);
            setNote("");
            await loadPatient();
            onChanged();
        } catch (err) {
            setStatusError(err instanceof ApiError ? err.message : "Xatolik yuz berdi");
        } finally {
            setIsSubmittingStatus(false);
        }
    };

    const handleScheduleClick = () => {
        if (!patient) return;
        onOpenChange(false);
        navigate(`/calendar?book=${patient.id}&bookName=${encodeURIComponent(patient.full_name)}`);
    };

    const handleUpload = async () => {
        if (!uploadFile || !patient) return;
        setUploadError(null);
        setIsUploading(true);
        try {
            const formData = new FormData();
            formData.append("file", uploadFile);
            await api.postForm(`/patients/${patient.id}/analysis`, formData);
            setUploadFile(null);
            await loadPatient();
            onChanged();
        } catch (err) {
            setUploadError(err instanceof ApiError ? err.message : "Yuklashda xatolik");
        } finally {
            setIsUploading(false);
        }
    };

    const handleGenerateAiReport = async (analysisId: string) => {
        setAiError(null);
        setAiLoadingId(analysisId);
        try {
            await api.post(`/analysis/${analysisId}/ai-report`);
            await loadPatient();
        } catch (err) {
            setAiError(err instanceof ApiError ? err.message : "AI tahlilida xatolik");
        } finally {
            setAiLoadingId(null);
        }
    };

    const handleViewFile = async (analysisId: string) => {
        try {
            const blob = await fetchBlob(`/analysis/${analysisId}/file`);
            window.open(URL.createObjectURL(blob), "_blank");
        } catch {
            setUploadError("Faylni ochib bo'lmadi");
        }
    };

    const doneStatuses = new Set(patient?.history.map((h) => h.to_status) ?? []);
    const nextStatuses = patient ? (VALID_TRANSITIONS[patient.status] ?? []) : [];
    const upcomingAppointment = patient?.appointments.find((a) => a.status === "scheduled");

    return (
        <SlideoutMenu isOpen={!!patientId} onOpenChange={(open) => !open && onOpenChange(false)}>
            {({ close }) => (
                <>
                    <SlideoutMenu.Header onClose={close}>
                        {patient && (
                            <div className="flex flex-col gap-1.5 pr-8">
                                <h2 className="text-lg font-semibold text-primary">{patient.full_name}</h2>
                                <div className="flex items-center gap-2">
                                    <StatusBadge status={patient.status} />
                                    <span className="text-sm text-tertiary">{patient.phone}</span>
                                </div>
                            </div>
                        )}
                    </SlideoutMenu.Header>

                    <SlideoutMenu.Content>
                        {isLoading && <p className="text-sm text-tertiary">Yuklanmoqda...</p>}
                        {loadError && <p className="text-sm text-error-primary">{loadError}</p>}

                        {patient && (
                            <div className="flex flex-col gap-8 pb-8">
                                <div className="flex flex-col gap-1 text-sm text-secondary">
                                    {patient.telegram_username && <p>Telegram: @{patient.telegram_username}</p>}
                                    {patient.consultation_goal && <p>Maqsad: {patient.consultation_goal}</p>}
                                    {upcomingAppointment && <p>Qabul: {formatDateTime(upcomingAppointment.start_at)}</p>}
                                    <p className="text-tertiary">
                                        {patient.source === "bot" ? "Bot orqali" : "Qo'lda"} qo'shilgan · {formatDateTime(patient.created_at)}
                                    </p>
                                </div>

                                <div>
                                    <p className="mb-3 text-sm font-semibold text-secondary">Bosqichlar</p>
                                    <ol className="flex flex-col">
                                        {STATUS_ORDER.map((s, idx) => {
                                            const isDone = doneStatuses.has(s);
                                            const isLast = idx === STATUS_ORDER.length - 1;
                                            return (
                                                <li key={s} className="relative flex gap-3 pb-6 last:pb-0">
                                                    {!isLast && (
                                                        <div
                                                            className={cx(
                                                                "absolute top-6 left-[11px] h-full w-px",
                                                                isDone ? "bg-fg-brand-primary" : "bg-border-secondary",
                                                            )}
                                                        />
                                                    )}
                                                    <div
                                                        className={cx(
                                                            "relative z-1 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                                                            isDone
                                                                ? "bg-brand-solid text-white"
                                                                : "bg-secondary text-tertiary ring-1 ring-secondary",
                                                        )}
                                                    >
                                                        {isDone ? <Check className="size-3.5" /> : idx + 1}
                                                    </div>
                                                    <span className={cx("pt-0.5 text-sm", isDone ? "font-medium text-primary" : "text-tertiary")}>
                                                        {STATUS_LABELS[s]}
                                                    </span>
                                                </li>
                                            );
                                        })}
                                    </ol>
                                </div>

                                {canManageStatus && nextStatuses.length > 0 && (
                                    <div className="flex flex-col gap-3">
                                        <p className="text-sm font-semibold text-secondary">Holatni o'zgartirish</p>
                                        {!pendingStatus ? (
                                            <div className="flex flex-wrap gap-2">
                                                {nextStatuses.map((s) => (
                                                    <Button
                                                        key={s}
                                                        size="sm"
                                                        color="secondary"
                                                        onClick={() => (s === "scheduled" ? handleScheduleClick() : setPendingStatus(s))}
                                                    >
                                                        {STATUS_LABELS[s]}
                                                    </Button>
                                                ))}
                                            </div>
                                        ) : (
                                            <div className="flex flex-col gap-3 rounded-lg bg-secondary p-3 ring-1 ring-secondary">
                                                <p className="text-sm text-secondary">
                                                    Yangi holat: <strong className="text-primary">{STATUS_LABELS[pendingStatus]}</strong>
                                                </p>
                                                <TextArea label="Izoh (ixtiyoriy)" value={note} onChange={setNote} rows={2} />
                                                {statusError && <p className="text-sm text-error-primary">{statusError}</p>}
                                                <div className="flex justify-end gap-2">
                                                    <Button
                                                        size="sm"
                                                        color="secondary"
                                                        onClick={() => {
                                                            setPendingStatus(null);
                                                            setStatusError(null);
                                                        }}
                                                    >
                                                        Bekor qilish
                                                    </Button>
                                                    <Button size="sm" isLoading={isSubmittingStatus} onClick={handleConfirmStatus}>
                                                        Tasdiqlash
                                                    </Button>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}

                                <div className="flex flex-col gap-3">
                                    <p className="text-sm font-semibold text-secondary">Analiz yuklash</p>
                                    <input
                                        type="file"
                                        onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                                        className="text-sm text-tertiary file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-secondary"
                                    />
                                    {uploadError && <p className="text-sm text-error-primary">{uploadError}</p>}
                                    <Button
                                        size="sm"
                                        iconLeading={UploadCloud02}
                                        isLoading={isUploading}
                                        isDisabled={!uploadFile}
                                        onClick={handleUpload}
                                        className="self-start"
                                    >
                                        Yuklash va bemorga yuborish
                                    </Button>
                                </div>

                                <div className="flex flex-col gap-2">
                                    <p className="text-sm font-semibold text-secondary">Hujjatlar</p>
                                    {patient.analyses.length === 0 && <p className="text-sm text-tertiary">Hozircha hujjatlar yo'q</p>}
                                    {aiError && <p className="text-sm text-error-primary">{aiError}</p>}
                                    {patient.analyses.map((a) => (
                                        <div key={a.id} className="flex flex-col gap-2 rounded-lg bg-secondary px-3 py-2">
                                            <div className="flex items-center justify-between gap-2">
                                                <div className="min-w-0">
                                                    <p className="truncate text-sm text-primary">{a.file_name || "Fayl"}</p>
                                                    <p className="text-xs text-tertiary">
                                                        {a.uploaded_by === "staff" ? "Klinika yukladi" : "Bemor yukladi"} ·{" "}
                                                        {formatDateTime(a.created_at)}
                                                    </p>
                                                </div>
                                                <div className="flex shrink-0 gap-1.5">
                                                    <Button size="sm" color="tertiary" onClick={() => handleViewFile(a.id)}>
                                                        Ko'rish
                                                    </Button>
                                                    {!a.ai_report && (
                                                        <Button
                                                            size="sm"
                                                            color="secondary"
                                                            iconLeading={Stars02}
                                                            isLoading={aiLoadingId === a.id}
                                                            onClick={() => handleGenerateAiReport(a.id)}
                                                        >
                                                            AI tahlil
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                            {a.ai_report && (
                                                <div className="rounded-md bg-primary p-2.5 ring-1 ring-secondary">
                                                    <p className="text-xs whitespace-pre-wrap text-secondary">{a.ai_report}</p>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>

                                <div className="flex flex-col gap-2">
                                    <p className="text-sm font-semibold text-secondary">Tarix</p>
                                    <ul className="flex flex-col gap-3">
                                        {patient.history.map((h) => (
                                            <li key={h.id} className="text-sm">
                                                <p className="text-primary">
                                                    {h.from_status ? `${STATUS_LABELS[h.from_status]} → ` : ""}
                                                    <strong>{STATUS_LABELS[h.to_status]}</strong>
                                                </p>
                                                <p className="text-xs text-tertiary">
                                                    {formatDateTime(h.at)}
                                                    {h.staff_name ? ` · ${h.staff_name}` : ""}
                                                </p>
                                                {h.note && <p className="mt-0.5 text-xs text-secondary">{h.note}</p>}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        )}
                    </SlideoutMenu.Content>
                </>
            )}
        </SlideoutMenu>
    );
};
