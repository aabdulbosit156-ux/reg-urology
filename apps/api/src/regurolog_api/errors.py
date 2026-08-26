from dataclasses import dataclass, field

from regurolog_api.contracts import FieldError


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    field_errors: list[FieldError] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
