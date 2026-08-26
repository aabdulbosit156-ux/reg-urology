import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from regurolog_api.config import Settings
from regurolog_api.crypto import qr_data_url
from regurolog_api.models import AuthChallenge, BotConnection, Session, StaffUser
from regurolog_api.security import constant_time_token_matches, keyed_digest, random_opaque_token


@dataclass(frozen=True, slots=True)
class ChallengeCreated:
    challenge: AuthChallenge
    deep_link: str
    qr_data_url: str
    browser_binding: str


@dataclass(frozen=True, slots=True)
class StaffSessionCreated:
    staff: StaffUser
    session: Session
    session_token: str
    csrf_token: str


class StaffAuthService:
    def __init__(self, settings: Settings) -> None:
        if settings.session_secret is None:
            raise RuntimeError("SESSION_SECRET sozlanmagan")
        self.settings = settings
        self.secret = settings.session_secret.get_secret_value()

    def digest(self, namespace: str, token: str) -> str:
        return keyed_digest(f"{namespace}:{token}", self.secret)

    async def create_challenge(
        self,
        db_session: AsyncSession,
        *,
        now: datetime | None = None,
    ) -> ChallengeCreated:
        current_time = now or datetime.now(UTC)
        connection = await db_session.scalar(
            select(BotConnection).where(
                BotConnection.active.is_(True), BotConnection.status == "connected"
            )
        )
        if connection is None:
            raise RuntimeError("Bot hali ulanmagan")

        login_token = random_opaque_token()
        browser_binding = random_opaque_token()
        challenge = AuthChallenge(
            token_hash=self.digest("login", login_token),
            browser_binding_hash=self.digest("browser", browser_binding),
            matching_code=f"{secrets.randbelow(1_000_000):06d}",
            state="pending",
            expires_at=current_time + timedelta(seconds=self.settings.login_challenge_ttl_seconds),
            created_at=current_time,
        )
        db_session.add(challenge)
        await db_session.flush()
        deep_link = f"https://t.me/{connection.username}?start=login_{login_token}"
        return ChallengeCreated(
            challenge=challenge,
            deep_link=deep_link,
            qr_data_url=qr_data_url(deep_link),
            browser_binding=browser_binding,
        )

    async def challenge_for_binding(
        self,
        db_session: AsyncSession,
        browser_binding: str,
        *,
        for_update: bool = False,
        now: datetime | None = None,
    ) -> AuthChallenge | None:
        current_time = now or datetime.now(UTC)
        statement = (
            select(AuthChallenge)
            .where(AuthChallenge.browser_binding_hash == self.digest("browser", browser_binding))
            .order_by(AuthChallenge.created_at.desc())
        )
        if for_update:
            statement = statement.with_for_update()
        challenge = await db_session.scalar(statement)
        if (
            challenge
            and challenge.expires_at <= current_time
            and challenge.state
            not in {
                "consumed",
                "rejected",
            }
        ):
            challenge.state = "expired"
        return challenge

    async def claim_from_telegram(
        self,
        db_session: AsyncSession,
        *,
        login_token: str,
        telegram_user_id: int,
        now: datetime | None = None,
    ) -> AuthChallenge | None:
        current_time = now or datetime.now(UTC)
        challenge = await db_session.scalar(
            select(AuthChallenge)
            .where(AuthChallenge.token_hash == self.digest("login", login_token))
            .with_for_update()
        )
        if (
            challenge is None
            or challenge.expires_at <= current_time
            or challenge.state != "pending"
        ):
            return None
        staff = await db_session.scalar(
            select(StaffUser).where(
                StaffUser.telegram_user_id == telegram_user_id,
                StaffUser.state == "active",
            )
        )
        if staff is None:
            return None
        challenge.telegram_user_id = telegram_user_id
        challenge.staff_id = staff.id
        challenge.state = "awaiting_confirmation"
        return challenge

    async def confirm_from_telegram(
        self,
        db_session: AsyncSession,
        *,
        challenge_id: str,
        telegram_user_id: int,
        approved: bool,
        now: datetime | None = None,
    ) -> bool:
        current_time = now or datetime.now(UTC)
        try:
            from uuid import UUID

            parsed_id = UUID(challenge_id)
        except ValueError:
            return False
        challenge = await db_session.scalar(
            select(AuthChallenge).where(AuthChallenge.id == parsed_id).with_for_update()
        )
        if (
            challenge is None
            or challenge.telegram_user_id != telegram_user_id
            or challenge.state != "awaiting_confirmation"
            or challenge.expires_at <= current_time
        ):
            return False
        challenge.state = "approved" if approved else "rejected"
        return True

    async def exchange(
        self,
        db_session: AsyncSession,
        browser_binding: str,
        *,
        now: datetime | None = None,
    ) -> StaffSessionCreated | None:
        current_time = now or datetime.now(UTC)
        challenge = await self.challenge_for_binding(
            db_session, browser_binding, for_update=True, now=current_time
        )
        if (
            challenge is None
            or challenge.state != "approved"
            or challenge.staff_id is None
            or challenge.expires_at <= current_time
        ):
            return None
        staff = await db_session.scalar(
            select(StaffUser)
            .where(StaffUser.id == challenge.staff_id, StaffUser.state == "active")
            .with_for_update()
        )
        if staff is None:
            return None

        session_token = random_opaque_token()
        csrf_token = random_opaque_token()
        session = Session(
            token_hash=self.digest("session", session_token),
            principal_type="staff",
            staff_id=staff.id,
            auth_epoch=staff.auth_epoch,
            csrf_token_hash=self.digest("csrf", csrf_token),
            expires_at=current_time + timedelta(seconds=self.settings.staff_session_ttl_seconds),
            last_seen_at=current_time,
            created_at=current_time,
        )
        challenge.state = "consumed"
        challenge.consumed_at = current_time
        db_session.add(session)
        await db_session.flush()
        return StaffSessionCreated(
            staff=staff,
            session=session,
            session_token=session_token,
            csrf_token=csrf_token,
        )

    async def authenticate(
        self,
        db_session: AsyncSession,
        token: str,
        *,
        now: datetime | None = None,
    ) -> tuple[Session, StaffUser] | None:
        current_time = now or datetime.now(UTC)
        row = (
            await db_session.execute(
                select(Session, StaffUser)
                .join(StaffUser, StaffUser.id == Session.staff_id)
                .where(
                    Session.token_hash == self.digest("session", token),
                    Session.principal_type == "staff",
                )
            )
        ).one_or_none()
        if row is None:
            return None
        session, staff = row
        idle_limit = timedelta(seconds=self.settings.staff_idle_timeout_seconds)
        invalid = (
            session.revoked_at is not None
            or session.expires_at <= current_time
            or current_time - session.last_seen_at > idle_limit
            or staff.state != "active"
            or not constant_time_token_matches(session.auth_epoch, staff.auth_epoch)
        )
        if invalid:
            if session.revoked_at is None:
                session.revoked_at = current_time
            return None
        session.last_seen_at = current_time
        return session, staff

    def csrf_matches(self, session: Session, csrf_token: str) -> bool:
        return constant_time_token_matches(
            session.csrf_token_hash,
            self.digest("csrf", csrf_token),
        )
