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

const AUDIT_ACTION: Record<string, string> = {
  "patient.contact_viewed": "Bemor kartochkasi ko‘rildi",
  "patient.updated": "Bemor ma’lumoti yangilandi",
  "inquiry.assigned": "Murojaat biriktirildi",
  "inquiry.closed": "Murojaat yopildi",
  "inquiry.reopened": "Murojaat qayta ochildi",
  "inquiry.released": "Biriktiruv bekor qilindi",
  "contact.started": "Aloqa boshlandi",
  "contact.finished": "Aloqa yakunlandi",
  "contact.note_added": "Izoh qo‘shildi",
  "reception_sheet.viewed": "Qabul varaqasi ko‘rildi",
  "reception_sheet.print_viewed": "Varaqa chop uchun ko‘rildi",
  "campaign.created": "Kampaniya yaratildi",
  "campaign.archived": "Kampaniya arxivlandi",
  "campaign.revoked": "Kampaniya bekor qilindi",
  "settings.draft_created": "Sozlama qoralamasi",
  "settings.rollback_draft_created": "Sozlama qaytarish qoralamasi",
  "settings.published": "Sozlama e’lon qilindi",
  "auth.logout": "Tizimdan chiqdi",
  "auth.challenge_created": "Kirish so‘rovi",
  "auth.exchange_succeeded": "Tizimga kirdi",
  "staff.invite_created": "Xodim taklifi yaratildi",
  "staff.invite_approved": "Xodim tasdiqlandi",
  "staff.deactivated": "Xodim bloklandi",
  "bot.connected": "Bot ulandi",
  "root.login_rate_limited": "Root: urinishlar cheklandi",
  "root.login_failed": "Root: kirish xatosi",
  "root.login_succeeded": "Root: kirdi",
  "doctor.updated": "Doktor ma’lumoti yangilandi",
  "schedule.version_created": "Ish jadvali yangilandi",
  "schedule.override_saved": "Sana istisnosi saqlandi",
  "schedule.block_created": "Band vaqt qo‘shildi",
  "appointment.created": "Qabul yaratildi",
  "appointment.rescheduled": "Qabul ko‘chirildi",
  "appointment.transitioned": "Qabul holati o‘zgardi",
  "appointment.corrected": "Qabul tuzatildi",
};

export const actionLabel = (value: string) => AUDIT_ACTION[value] ?? value;

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
