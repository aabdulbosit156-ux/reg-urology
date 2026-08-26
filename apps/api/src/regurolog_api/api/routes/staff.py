from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from regurolog_api.api.dependencies import (
    CurrentPrincipal,
    ensure_role,
    get_database,
    get_settings,
    require_csrf,
    require_principal,
)
from regurolog_api.config import Settings
from regurolog_api.contracts import StaffRole
from regurolog_api.database import Database
from regurolog_api.errors import ApiError
from regurolog_api.models import StaffInvite, StaffUser
from regurolog_api.schemas import InviteCreateRequest, InviteResponse, StaffResponse
from regurolog_api.services.audit import add_audit
from regurolog_api.services.staff import StaffService

router = APIRouter()
SettingsDependency = Annotated[Settings, Depends(get_settings)]
DatabaseDependency = Annotated[Database, Depends(get_database)]
PrincipalDependency = Annotated[CurrentPrincipal, Depends(require_principal)]
MANAGER_ROLES = {StaffRole.DEV, StaffRole.DIRECTOR}


def invite_state(invite: StaffInvite, now: datetime) -> str:
    if invite.revoked_at:
        return "revoked"
    if invite.approved_at:
        return "approved"
    if invite.expires_at <= now:
        return "expired"
    if invite.claimed_telegram_user_id:
        return "pending_approval"
    return "pending_claim"


@router.get("", response_model=list[StaffResponse])
async def list_staff(
    current: PrincipalDependency,
    database: DatabaseDependency,
) -> list[StaffResponse]:
    ensure_role(current, MANAGER_ROLES)
    async with database.session_factory() as db_session:
        staff = list(
            (await db_session.scalars(select(StaffUser).order_by(StaffUser.created_at))).all()
        )
    return [
        StaffResponse(
            id=item.id,
            telegram_user_id=item.telegram_user_id,
            telegram_username=item.telegram_username,
            full_name=item.full_name,
            role=StaffRole(item.role),
            state=item.state,
            created_at=item.created_at,
        )
        for item in staff
    ]


@router.get("/invites", response_model=list[InviteResponse])
async def list_invites(
    current: PrincipalDependency,
    database: DatabaseDependency,
) -> list[InviteResponse]:
    ensure_role(current, MANAGER_ROLES)
    statement = select(StaffInvite).order_by(StaffInvite.created_at.desc())
    if current.kind == "staff":
        if current.staff is None:
            raise ApiError(401, "AUTH_REQUIRED", "Sessiya haqiqiy emas")
        statement = statement.where(StaffInvite.issuer_id == current.staff.id)
    async with database.session_factory() as db_session:
        invites = list((await db_session.scalars(statement)).all())
    now = datetime.now(UTC)
    return [
        InviteResponse(
            id=item.id,
            role=StaffRole(item.role),
            state=invite_state(item, now),
            expires_at=item.expires_at,
            claimed_full_name=item.claimed_full_name,
            claimed_username=item.claimed_username,
        )
        for item in invites
    ]


@router.post("/invites", response_model=InviteResponse, status_code=201)
async def create_invite(
    payload: InviteCreateRequest,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> InviteResponse:
    ensure_role(current, MANAGER_ROLES)
    require_csrf(request, settings, current)
    if current.role is StaffRole.DIRECTOR and payload.role is StaffRole.DIRECTOR:
        raise ApiError(
            403, "ROLE_ESCALATION_FORBIDDEN", "Director boshqa director taklif qila olmaydi"
        )
    service = StaffService(settings)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            try:
                created = await service.create_invite(
                    db_session,
                    role=payload.role.value,
                    issuer_kind=current.kind,
                    issuer_id=current.staff.id if current.staff else None,
                )
            except RuntimeError as error:
                raise ApiError(409, "BOT_NOT_CONFIGURED", "Avval Telegram botni ulang") from error
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="staff.invite_created",
                entity_type="staff_invite",
                entity_id=created.invite.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
                changes={"role": payload.role.value},
            )
    return InviteResponse(
        id=created.invite.id,
        role=payload.role,
        state="pending_claim",
        expires_at=created.invite.expires_at,
        deep_link=created.deep_link,
        qr_data_url=created.qr_data_url,
    )


@router.post("/invites/{invite_id}/approve", response_model=StaffResponse)
async def approve_invite(
    invite_id: UUID,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> StaffResponse:
    ensure_role(current, MANAGER_ROLES)
    require_csrf(request, settings, current)
    service = StaffService(settings)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            invite = await db_session.scalar(
                select(StaffInvite).where(StaffInvite.id == invite_id).with_for_update()
            )
            if invite is None:
                raise ApiError(404, "INVITE_NOT_FOUND", "Taklif topilmadi")
            if current.kind == "staff" and invite.issuer_id != current.staff.id:  # type: ignore[union-attr]
                raise ApiError(403, "FORBIDDEN", "Faqat o‘zingiz yaratgan taklifni tasdiqlaysiz")
            if current.role is StaffRole.DIRECTOR and invite.role != StaffRole.ADMIN.value:
                raise ApiError(403, "ROLE_ESCALATION_FORBIDDEN", "Bu rolni tasdiqlash mumkin emas")
            staff = await service.approve_invite(db_session, invite)
            if staff is None:
                raise ApiError(
                    409, "INVITE_NOT_APPROVABLE", "Taklif eskirgan yoki claim qilinmagan"
                )
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="staff.invite_approved",
                entity_type="staff_user",
                entity_id=staff.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
                changes={"role": staff.role},
            )
    return StaffResponse(
        id=staff.id,
        telegram_user_id=staff.telegram_user_id,
        telegram_username=staff.telegram_username,
        full_name=staff.full_name,
        role=StaffRole(staff.role),
        state=staff.state,
        created_at=staff.created_at,
    )


@router.post("/{staff_id}/deactivate", response_model=StaffResponse)
async def deactivate_staff(
    staff_id: UUID,
    request: Request,
    current: PrincipalDependency,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> StaffResponse:
    ensure_role(current, MANAGER_ROLES)
    require_csrf(request, settings, current)
    async with database.session_factory() as db_session:
        async with db_session.begin():
            staff = await db_session.scalar(
                select(StaffUser).where(StaffUser.id == staff_id).with_for_update()
            )
            if staff is None:
                raise ApiError(404, "STAFF_NOT_FOUND", "Xodim topilmadi")
            if current.staff and current.staff.id == staff.id:
                raise ApiError(409, "SELF_DEACTIVATION_FORBIDDEN", "O‘zingizni bloklay olmaysiz")
            if current.role is StaffRole.DIRECTOR and staff.role != StaffRole.ADMIN.value:
                raise ApiError(403, "FORBIDDEN", "Director faqat adminni bloklay oladi")
            await StaffService(settings).deactivate(db_session, staff)
            add_audit(
                db_session,
                actor_kind=current.kind,
                actor_id=current.actor_id,
                action="staff.deactivated",
                entity_type="staff_user",
                entity_id=staff.id,
                request_id=request.state.request_id,
                occurred_at=datetime.now(UTC),
                changes={"state": "inactive"},
            )
    return StaffResponse(
        id=staff.id,
        telegram_user_id=staff.telegram_user_id,
        telegram_username=staff.telegram_username,
        full_name=staff.full_name,
        role=StaffRole(staff.role),
        state=staff.state,
        created_at=staff.created_at,
    )
