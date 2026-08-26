from datetime import UTC, datetime

import pytest
from regurolog_api.crypto import TokenCipher
from regurolog_api.domain.validation import (
    DomainValidationError,
    mask_phone,
    normalize_full_name,
    normalize_uz_phone,
    render_template,
    validate_weekly_intervals,
)
from regurolog_api.services.calendar import CalendarService


def test_patient_input_normalization_and_masking() -> None:
    assert normalize_full_name("  O‘tkir   Aliyev  ") == "O‘tkir Aliyev"
    assert normalize_uz_phone("99 123-45-67") == "+998991234567"
    assert mask_phone("+998991234567").endswith("67")
    with pytest.raises(DomainValidationError):
        normalize_full_name("Aliyev123")
    with pytest.raises(DomainValidationError):
        normalize_uz_phone("+997991234567")


def test_schedule_grid_and_safe_templates() -> None:
    weekly = validate_weekly_intervals(
        {"0": [{"start": "09:00", "end": "13:00"}], "1": [], "2": []}
    )
    assert weekly["0"] == [{"start": "09:00", "end": "13:00"}]
    assert set(weekly) == {str(day) for day in range(7)}
    local_start = datetime(2026, 8, 24, 12, 45, tzinfo=UTC).astimezone()
    assert isinstance(CalendarService._fits(weekly["0"], local_start), bool)
    assert render_template("Salom, {full_name}", {"full_name": "<Bemor>"}) == (
        "Salom, &lt;Bemor&gt;"
    )
    with pytest.raises(DomainValidationError):
        render_template("{__class__}", {})


def test_bot_token_cipher_does_not_store_plaintext() -> None:
    cipher = TokenCipher("test-encryption-secret-at-least-32-bytes")
    encrypted = cipher.encrypt("123456:telegram-token")
    assert "telegram-token" not in encrypted
    assert cipher.decrypt(encrypted) == "123456:telegram-token"
