// Manual Uzbek date/time formatting — browsers ship inconsistent (often incomplete) CLDR
// data for the "uz-UZ" locale, which makes Intl.DateTimeFormat fall back to raw patterns
// like "M09" for month names, and can default to 12-hour time. Formatting by hand
// sidesteps both problems and guarantees the same output on every browser.

const MONTHS = [
    "yanvar",
    "fevral",
    "mart",
    "aprel",
    "may",
    "iyun",
    "iyul",
    "avgust",
    "sentabr",
    "oktabr",
    "noyabr",
    "dekabr",
];

const MONTHS_SHORT = ["yan", "fev", "mar", "apr", "may", "iyun", "iyul", "avg", "sen", "okt", "noy", "dek"];

// Indexed by Date#getDay() (0 = Sunday).
const WEEKDAYS = ["yakshanba", "dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba"];
const WEEKDAYS_SHORT = ["Yak", "Du", "Se", "Chor", "Pay", "Ju", "Sha"];

function pad2(n: number): string {
    return String(n).padStart(2, "0");
}

function toDate(value: Date | string): Date {
    return typeof value === "string" ? new Date(value) : value;
}

/** "10.09.2026" */
export function formatDateUz(value: Date | string): string {
    const d = toDate(value);
    return `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}.${d.getFullYear()}`;
}

/** "10.09" — compact day.month, no year (e.g. chart axis labels). */
export function formatDayMonthUz(value: Date | string): string {
    const d = toDate(value);
    return `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}`;
}

/** "14:30", always 24-hour. */
export function formatTimeUz(value: Date | string): string {
    const d = toDate(value);
    return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** "10.09.2026 14:30" */
export function formatDateTimeUz(value: Date | string): string {
    return `${formatDateUz(value)} ${formatTimeUz(value)}`;
}

/** "Pay, 10.09" — short weekday + day.month, used for compact day headers. */
export function formatDayShortUz(value: Date | string): string {
    const d = toDate(value);
    return `${WEEKDAYS_SHORT[d.getDay()]}, ${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}`;
}

/** "sentabr 2026" */
export function formatMonthYearUz(value: Date | string): string {
    const d = toDate(value);
    return `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

/** "01 sen — 07 sen 2026" for the 7-day range starting at weekStart. */
export function formatWeekRangeUz(weekStart: Date): string {
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);
    const startLabel = `${pad2(weekStart.getDate())} ${MONTHS_SHORT[weekStart.getMonth()]}`;
    const endLabel = `${pad2(weekEnd.getDate())} ${MONTHS_SHORT[weekEnd.getMonth()]} ${weekEnd.getFullYear()}`;
    return `${startLabel} — ${endLabel}`;
}

/** "payshanba, 10 sentabr 2026" */
export function formatFullDateUz(value: Date | string): string {
    const d = toDate(value);
    return `${WEEKDAYS[d.getDay()]}, ${pad2(d.getDate())} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}
