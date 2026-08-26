from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from regurolog_api.config import Settings
from regurolog_api.crypto import qr_data_url
from regurolog_api.models import (
    AuthChallenge,
    BotConnection,
    Inquiry,
    Session,
    StaffInvite,
    StaffUser,
)
from regurolog_api.security import keyed_digest, random_opaque_token


@dataclass(frozen=True, slots=True)
class InviteCreated:
    invite: StaffInvite
    deep_link: str
    qr_data_url: str


class StaffService:
    def __init__(self, settings: Settings) -> None:
        if settings.session_secret is None:
            raise RuntimeError("SESSION_SECRET sozlanmagan")
        self.settings = settings
        self.secret = settings.session_secret.get_secret_value()

    def invite_hash(self, token: str) -> str:
        return keyed_digest(f"invite:{token}", self.secret)

    async def create_invite(
        self,
        db_session: AsyncSession,
        *,
        role: str,
        issuer_kind: str,
        issuer_id: UUID | None,
        now: datetime | None = None,
    ) -> InviteCreated:
        current_time = now or datetime.now(UTC)
        connection = await db_session.scalar(
            select(BotConnection).where(
                BotConnection.active.is_(True), BotConnection.status == "connected"
            )
        )
        if connection is None:
            raise RuntimeError("Bot hali ulanmagan")
        token = random_opaque_token()
        invite = StaffInvite(
            token_hash=self.invite_hash(token),
            role=role,
            issuer_kind=issuer_kind,
            issuer_id=issuer_id,
            expires_at=current_time + timedelta(seconds=self.settings.invite_ttl_seconds),
            created_at=current_time,
        )
        db_session.add(invite)
        await db_session.flush()
        deep_link = f"https://t.me/{connection.username}?start=invite_{token}"
        return InviteCreated(invite=invite, deep_link=deep_link, qr_data_url=qr_data_url(deep_link))

    async def claim_invite(
        self,
        db_session: AsyncSession,
        *,
        token: str,
        telegram_user_id: int,
        full_name: str,
        username: str | None,
        now: datetime | None = None,
    ) -> StaffInvite | None:
        current_time = now or datetime.now(UTC)
        invite = await db_session.scalar(
            select(StaffInvite)
            .where(StaffInvite.token_hash == self.invite_hash(token))
            .with_for_update()
        )
        if (
            invite is None
            or invite.expires_at <= current_time
            or invite.revoked_at is not None
            or invite.approved_at is not None
            or invite.claimed_telegram_user_id is not None
        ):
            return None
        invite.claimed_telegram_user_id = telegram_user_id
        invite.claimed_full_name = full_name
        invite.claimed_username = username
        return invite

    async def approve_invite(
        self,
        db_session: AsyncSession,
        invite: StaffInvite,
        *,
        now: datetime | None = None,
    ) -> StaffUser | None:
        current_time = now or datetime.now(UTC)
        if (
            invite.claimed_telegram_user_id is None
            or invite.claimed_full_name is None
            or invite.approved_at is not None
            or invite.revoked_at is not None
            or invite.expires_at <= current_time
        ):
            return None
        existing = await db_session.scalar(
            select(StaffUser).where(StaffUser.telegram_user_id == invite.claimed_telegram_user_id)
        )
        if existing is not None:
            return None
        staff = StaffUser(
            telegram_user_id=invite.claimed_telegram_user_id,
            telegram_username=invite.claimed_username,
            full_name=invite.claimed_full_name,
            role=invite.role,
            state="active",
            invited_by=invite.issuer_id,
            created_at=current_time,
            updated_at=current_time,
        )
        db_session.add(staff)
        await db_session.flush()
        invite.claimed_by = staff.id
        invite.approved_at = current_time
        return staff

    async def deactivate(
        self,
        db_session: AsyncSession,
        staff: StaffUser,
        *,
        now: datetime | None = None,
    ) -> None:
        current_time = now or datetime.now(UTC)
        staff.state = "inactive"
        staff.deactivated_at = current_time
        staff.updated_at = current_time
        staff.auth_epoch = random_opaque_token()
        await db_session.execute(
            update(Session)
            .where(Session.staff_id == staff.id, Session.revoked_at.is_(None))
            .values(revoked_at=current_time)
        )
        await db_session.execute(
            update(AuthChallenge)
            .where(
                AuthChallenge.staff_id == staff.id,
                AuthChallenge.state.in_(["pending", "awaiting_confirmation", "approved"]),
            )
            .values(state="rejected")
        )
        await db_session.execute(
            update(Inquiry)
            .where(Inquiry.assigned_to == staff.id, Inquiry.status == "open")
            .values(assigned_to=None, version=Inquiry.version + 1, updated_at=current_time)
        )
