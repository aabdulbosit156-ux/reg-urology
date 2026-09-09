import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.core.security import decode_access_token
from app.database import get_db  # noqa: F401  (re-exported for route modules)
from app.models.staff import StaffRole

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentPrincipal:
    sub: str
    role: StaffRole


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentPrincipal:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    return CurrentPrincipal(sub=payload["sub"], role=StaffRole(payload["role"]))


def require_roles(*roles: StaffRole):
    def dependency(principal: CurrentPrincipal = Depends(get_current_principal)) -> CurrentPrincipal:
        if principal.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return principal

    return dependency


def require_bot_secret(x_bot_secret: str = Header(...)) -> None:
    if x_bot_secret != settings.bot_internal_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid bot secret")


def staff_id_or_none(principal: CurrentPrincipal) -> uuid.UUID | None:
    if principal.role == StaffRole.dev and principal.sub == "dev":
        return None
    return uuid.UUID(principal.sub)
