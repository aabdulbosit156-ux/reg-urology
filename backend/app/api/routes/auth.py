import io
from datetime import UTC, datetime, timedelta

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentPrincipal,
    get_current_principal,
    get_db,
    require_bot_secret,
    require_roles,
)
from app.config import get_settings
from app.core.security import create_access_token, generate_session_token, verify_password
from app.core.telegram_auth import InvalidInitData, verify_login_widget, verify_webapp_init_data
from app.models.staff import Staff, StaffRole
from app.models.staff_session import StaffSession, StaffSessionStatus
from app.schemas.auth import (
    DevLoginRequest,
    MeResponse,
    StaffSessionConfirmRequest,
    StaffSessionConfirmResponse,
    StaffSessionCreateRequest,
    StaffSessionCreateResponse,
    StaffTelegramLoginRequest,
    StaffWebAppLoginRequest,
    TokenResponse,
)
from app.services import telegram

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/dev-login", response_model=TokenResponse)
def dev_login(payload: DevLoginRequest) -> TokenResponse:
    if not settings.dev_password_hash:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Dev login is not configured")
    if payload.username != settings.dev_username or not verify_password(
        payload.password, settings.dev_password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = create_access_token(subject="dev", role=StaffRole.dev)
    return TokenResponse(access_token=token, role=StaffRole.dev, expires_in=settings.jwt_expire_minutes * 60)


@router.post(
    "/staff/token",
    response_model=StaffSessionCreateResponse,
    dependencies=[Depends(require_roles(StaffRole.dev, StaffRole.director))],
)
async def create_staff_session(
    payload: StaffSessionCreateRequest, db: AsyncSession = Depends(get_db)
) -> StaffSessionCreateResponse:
    token = generate_session_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.staff_session_ttl_minutes)
    session = StaffSession(token=token, role=payload.role, expires_at=expires_at)
    db.add(session)
    await db.commit()

    bot_username = await telegram.resolve_bot_username(db)
    deep_link = f"https://t.me/{bot_username}?start=staff_{token}" if bot_username else ""
    return StaffSessionCreateResponse(
        token=token, role=payload.role, deep_link=deep_link, expires_at=expires_at
    )


@router.get(
    "/staff/token/{token}/qr",
    dependencies=[Depends(require_roles(StaffRole.dev, StaffRole.director))],
)
async def get_staff_session_qr(token: str, db: AsyncSession = Depends(get_db)) -> Response:
    result = await db.execute(select(StaffSession).where(StaffSession.token == token))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    bot_username = await telegram.resolve_bot_username(db)
    if not bot_username:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Bot username is not configured")

    deep_link = f"https://t.me/{bot_username}?start=staff_{token}"
    img = qrcode.make(deep_link)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@router.post(
    "/staff/confirm",
    response_model=StaffSessionConfirmResponse,
    dependencies=[Depends(require_bot_secret)],
)
async def confirm_staff_session(
    payload: StaffSessionConfirmRequest, db: AsyncSession = Depends(get_db)
) -> StaffSessionConfirmResponse:
    result = await db.execute(select(StaffSession).where(StaffSession.token == payload.token))
    session = result.scalar_one_or_none()
    if session is None or session.status != StaffSessionStatus.pending:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found or already used")
    if session.expires_at < datetime.now(UTC):
        session.status = StaffSessionStatus.expired
        await db.commit()
        raise HTTPException(status.HTTP_410_GONE, "Session expired")

    result = await db.execute(
        select(Staff).where(Staff.telegram_user_id == payload.telegram_user_id)
    )
    staff = result.scalar_one_or_none()
    if staff is None:
        staff = Staff(
            role=session.role,
            full_name=payload.full_name,
            telegram_user_id=payload.telegram_user_id,
            phone=payload.phone,
        )
        db.add(staff)
        await db.flush()
    else:
        staff.role = session.role
        staff.full_name = payload.full_name
        staff.is_active = True

    session.status = StaffSessionStatus.confirmed
    session.staff_id = staff.id
    await db.commit()

    return StaffSessionConfirmResponse(staff_id=staff.id, role=staff.role, full_name=staff.full_name)


@router.post("/staff/webapp-login", response_model=TokenResponse)
async def staff_webapp_login(
    payload: StaffWebAppLoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    bot_token = await telegram.resolve_bot_token(db)
    if not bot_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Bot tokeni sozlanmagan")

    try:
        tg_user = verify_webapp_init_data(payload.init_data, bot_token)
    except InvalidInitData as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    result = await db.execute(select(Staff).where(Staff.telegram_user_id == tg_user["id"]))
    staff = result.scalar_one_or_none()
    if staff is None or not staff.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Siz xodim sifatida ro'yxatdan o'tmagansiz")

    access_token = create_access_token(subject=str(staff.id), role=staff.role)
    return TokenResponse(
        access_token=access_token, role=staff.role, expires_in=settings.jwt_expire_minutes * 60
    )


@router.post("/staff/telegram-login", response_model=TokenResponse)
async def staff_telegram_login(
    payload: StaffTelegramLoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Website login via the Telegram Login Widget (normal browser) — for director/admin/analyst."""
    bot_token = await telegram.resolve_bot_token(db)
    if not bot_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Bot tokeni sozlanmagan")

    try:
        verify_login_widget(payload.model_dump(), bot_token)
    except InvalidInitData as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    result = await db.execute(select(Staff).where(Staff.telegram_user_id == payload.id))
    staff = result.scalar_one_or_none()
    if staff is None or not staff.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Siz xodim sifatida ro'yxatdan o'tmagansiz")

    access_token = create_access_token(subject=str(staff.id), role=staff.role)
    return TokenResponse(
        access_token=access_token, role=staff.role, expires_in=settings.jwt_expire_minutes * 60
    )


@router.get("/me", response_model=MeResponse)
async def me(
    principal: CurrentPrincipal = Depends(get_current_principal), db: AsyncSession = Depends(get_db)
) -> MeResponse:
    if principal.role == StaffRole.dev and principal.sub == "dev":
        return MeResponse(sub="dev", role=StaffRole.dev, full_name="Dev")

    result = await db.execute(select(Staff).where(Staff.id == principal.sub))
    staff = result.scalar_one_or_none()
    if staff is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff not found")
    return MeResponse(sub=str(staff.id), role=staff.role, full_name=staff.full_name)
