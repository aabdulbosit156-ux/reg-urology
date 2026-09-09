import type { AppointmentStatus, PatientStatus } from "@/types/patient";

export interface CalendarAppointmentPatient {
    id: string;
    full_name: string;
    phone: string;
    status: PatientStatus;
}

export interface CalendarAppointment {
    id: string;
    patient_id: string;
    staff_id: string | null;
    start_at: string;
    duration_min: number;
    status: AppointmentStatus;
    room: string | null;
    patient: CalendarAppointmentPatient;
}
