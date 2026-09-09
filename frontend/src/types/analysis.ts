export type AnalysisUploadedBy = "patient" | "staff";

export interface Analysis {
    id: string;
    patient_id: string;
    uploaded_by: AnalysisUploadedBy;
    file_name: string | null;
    mime_type: string | null;
    ordered: boolean;
    ai_report: string | null;
    created_at: string;
}
