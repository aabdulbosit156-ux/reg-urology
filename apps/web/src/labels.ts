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

export const appointmentStatusLabel = (value: string) => APPOINTMENT_STATUS[value] ?? value;
export const contactOutcomeLabel = (value: string) => CONTACT_OUTCOME[value] ?? value;
export const staffRoleLabel = (value: string) => STAFF_ROLE[value] ?? value;
export const botStatusLabel = (value: string) => BOT_STATUS[value] ?? value;
export const inquiryStatusLabel = (value: string) => INQUIRY_STATUS[value] ?? value;
