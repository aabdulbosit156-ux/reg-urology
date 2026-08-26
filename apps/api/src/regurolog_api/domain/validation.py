import html
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime, time, timedelta
from string import Formatter
from typing import Any

from regurolog_api.contracts import BUSINESS_TIMEZONE

NAME_PATTERN = re.compile(r"^[^\W\d_]+(?:[ '‘’ʼʻ-][^\W\d_]+)*$", re.UNICODE)
PHONE_INPUT_PATTERN = re.compile(r"^\+?[0-9 ()\-.]+$")
ALLOWED_TEMPLATE_FIELDS = {
    "full_name",
    "doctor_name",
    "date",
    "time",
    "clinic_address",
}


class DomainValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


def normalize_full_name(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not 2 <= len(normalized) <= 120:
        raise DomainValidationError("full_name", "Ism 2–120 belgidan iborat bo‘lishi kerak")
    if not NAME_PATTERN.fullmatch(normalized):
        raise DomainValidationError(
            "full_name",
            "Ismda faqat harflar, bo‘sh joy, apostrof va defis ishlating",
        )
    return normalized


def normalize_uz_phone(value: str) -> str:
    raw = value.strip()
    if not PHONE_INPUT_PATTERN.fullmatch(raw):
        raise DomainValidationError("phone", "Telefon raqamida harf yoki noto‘g‘ri belgi bor")
    if "+" in raw[1:]:
        raise DomainValidationError("phone", "+ belgisi faqat raqam boshida bo‘lishi mumkin")
    digits = "".join(character for character in raw if character.isdigit())
    if len(digits) == 9:
        digits = f"998{digits}"
    if len(digits) != 12 or not digits.startswith("998"):
        raise DomainValidationError(
            "phone", "O‘zbekiston raqamini +998XXXXXXXXX formatida kiriting"
        )
    return f"+{digits}"


def mask_phone(value: str) -> str:
    if len(value) != 13:
        return "••••"
    return f"{value[:4]} •• ••• •• {value[-2:]}"


def parse_grid_time(value: str) -> time:
    try:
        parsed = time.fromisoformat(value)
    except ValueError as error:
        raise DomainValidationError("intervals", "Vaqt HH:MM formatida bo‘lishi kerak") from error
    if parsed.second or parsed.microsecond or parsed.minute not in {0, 15, 30, 45}:
        raise DomainValidationError("intervals", "Vaqt 15 daqiqalik gridda bo‘lishi kerak")
    return parsed


def validate_intervals(intervals: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[tuple[time, time]] = []
    for interval in intervals:
        start = parse_grid_time(interval.get("start", ""))
        end = parse_grid_time(interval.get("end", ""))
        if end <= start:
            raise DomainValidationError("intervals", "Interval oxiri boshlanishidan keyin bo‘lsin")
        normalized.append((start, end))
    normalized.sort(key=lambda item: item[0])
    for previous, current in zip(normalized, normalized[1:], strict=False):
        if previous[1] > current[0]:
            raise DomainValidationError("intervals", "Ish vaqtlarida ustma-ust interval bor")
    return [
        {"start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")}
        for start, end in normalized
    ]


def validate_weekly_intervals(payload: Mapping[str, Any]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for weekday in range(7):
        value = payload.get(str(weekday), [])
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise DomainValidationError("weekly_intervals", "Haftalik jadval formati noto‘g‘ri")
        result[str(weekday)] = validate_intervals(value)
    return result


def local_day_bounds_utc(local_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(local_date, time.min, BUSINESS_TIMEZONE).astimezone(UTC)
    end = datetime.combine(local_date + timedelta(days=1), time.min, BUSINESS_TIMEZONE).astimezone(
        UTC
    )
    return start, end


def local_datetime_to_utc(local_date: date, local_time: time) -> datetime:
    return datetime.combine(local_date, local_time, BUSINESS_TIMEZONE).astimezone(UTC)


def tashkent_date(value: datetime) -> date:
    return value.astimezone(BUSINESS_TIMEZONE).date()


def render_template(template: str, values: Mapping[str, str]) -> str:
    if not template.strip():
        raise DomainValidationError("template", "Matn bo‘sh bo‘lishi mumkin emas")
    fields = {field_name for _, field_name, _, _ in Formatter().parse(template) if field_name}
    unknown = fields - ALLOWED_TEMPLATE_FIELDS
    if unknown:
        raise DomainValidationError(
            "template",
            f"Ruxsat etilmagan placeholder: {', '.join(sorted(unknown))}",
        )
    escaped_values = {key: html.escape(value) for key, value in values.items()}
    try:
        rendered = template.format_map(escaped_values)
    except KeyError as error:
        raise DomainValidationError(
            "template", f"Placeholder qiymati yo‘q: {error.args[0]}"
        ) from error
    if len(rendered) > 4096:
        raise DomainValidationError("template", "Telegram matni 4096 belgidan oshmasligi kerak")
    return rendered
