// Enum qiymatlarni foydalanuvchiga tushunarli o‘zbekcha yozuvlarga aylantiradi.
// Backenddan kelgan xom (inglizcha) qiymatlar UIda hech qachon ko‘rinmasligi kerak.

const APPOINTMENT_STATUS: Record<string, string> = {
  scheduled: "Rejalangan",
  checked_in: "Keldi",
  completed: "Yakunlandi",
  cancelled: "Bekor qilingan",
  no_show: "Kelmadi",
};

const CONTACT_OUTCOME: Record<string, string> = {
  in_progress: "Jarayonda",
  answered: "Javob berdi",
  no_answer: "Javob bermadi",
  busy: "Band",
  unreachable: "Aloqa yo‘q",
  wrong_number: "Noto‘g‘ri raqam",
  aborted: "Qo‘ng‘iroq qilinmadi",
  interrupted: "Uzilib qoldi",
};

const STAFF_ROLE: Record<string, string> = {
  DIRECTOR: "Direktor",
  ADMIN: "Administrator",
  DEV: "Dasturchi",
};

const BOT_STATUS: Record<string, string> = {
  connecting: "Ulanmoqda",
  connected: "Ulangan",
  error: "Xato",
  reconnect_required: "Qayta ulanish kerak",
};

const INQUIRY_STATUS: Record<string, string> = {
  open: "Ochiq",
  closed: "Yopilgan",
};

const CLOSE_REASON: Record<string, string> = {
  attended: "Keldi",
  declined: "Rad etdi",
  unreachable: "Aloqasiz",
  duplicate: "Dublikat",
  cancelled: "Bekor qilingan",
  other: "Boshqa",
};

export const appointmentStatusLabel = (value: string) => APPOINTMENT_STATUS[value] ?? value;
export const contactOutcomeLabel = (value: string) => CONTACT_OUTCOME[value] ?? value;
export const staffRoleLabel = (value: string) => STAFF_ROLE[value] ?? value;
export const botStatusLabel = (value: string) => BOT_STATUS[value] ?? value;
export const inquiryStatusLabel = (value: string) => INQUIRY_STATUS[value] ?? value;
export const closeReasonLabel = (value: string) => CLOSE_REASON[value] ?? value;

// The patient's effective status: "Ochiq" while the inquiry is open, otherwise
// the specific close reason (e.g. "Keldi", "Bekor qilingan").
export function patientStatusLabel(inquiryStatus: string | null, closeReason: string | null) {
  if (inquiryStatus === "open") return "Ochiq";
  if (inquiryStatus === "closed") return closeReason ? closeReasonLabel(closeReason) : "Yopilgan";
  return "—";
}

// The set of statuses an operator can assign to a patient.
export const PATIENT_STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "open", label: "Ochiq" },
  { value: "attended", label: "Keldi" },
  { value: "declined", label: "Rad etdi" },
  { value: "unreachable", label: "Aloqasiz" },
  { value: "duplicate", label: "Dublikat" },
  { value: "cancelled", label: "Bekor qilingan" },
  { value: "other", label: "Boshqa" },
];
