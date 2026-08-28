from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from regurolog_api.config import Settings
from regurolog_api.models import AuditEvent, AuthThrottle, Session
from regurolog_api.security import (
    auth_epoch,
    constant_time_token_matches,
    keyed_digest,
    random_opaque_token,
)


@dataclass(frozen=True, slots=True)
class LoginSuccess:
    session_token: str
    csrf_token: str
    session: Session


@dataclass(frozen=True, slots=True)
class LoginFailure:
    code: str
    retry_after_seconds: int | None = None


LoginResult = LoginSuccess | LoginFailure


class RootAuthService:
    def __init__(self, settings: Settings) -> None:
        if settings.admin_token is None or settings.session_secret is None:
            raise RuntimeError("Root autentifikatsiya sozlanmagan")
        self.settings = settings
        self.admin_token = settings.admin_token.get_secret_value()
        self.session_secret = settings.session_secret.get_secret_value()

    def source_key_hash(self, source: str) -> str:
        return keyed_digest(f"root-login:{source}", self.session_secret)

    def session_token_hash(self, token: str) -> str:
        return keyed_digest(f"session:{token}", self.session_secret)

    def csrf_token_hash(self, token: str) -> str:
        return keyed_digest(f"csrf:{token}", self.session_secret)

    async def login(
        self,
        db_session: AsyncSession,
        *,
        candidate: str,
        source: str,
        request_id: str,
        now: datetime | None = None,
    ) -> LoginResult:
        current_time = now or datetime.now(UTC)
        source_hash = self.source_key_hash(source)
        throttle = await self._locked_throttle(db_session, source_hash, current_time)

        if throttle.blocked_until and throttle.blocked_until > current_time:
            retry_after = max(1, int((throttle.blocked_until - current_time).total_seconds()))
            self._audit(
                db_session,
                action="root.login_rate_limited",
                request_id=request_id,
                source_key_hash=source_hash,
                now=current_time,
            )
            return LoginFailure(code="ROOT_LOGIN_RATE_LIMITED", retry_after_seconds=retry_after)

        window = timedelta(seconds=self.settings.root_login_window_seconds)
        if current_time - throttle.window_started_at >= window:
            throttle.failure_count = 0
            throttle.window_started_at = current_time
            throttle.blocked_until = None

        if not constant_time_token_matches(candidate, self.admin_token):
            throttle.failure_count += 1
            throttle.updated_at = current_time
            if throttle.failure_count >= self.settings.root_login_max_attempts:
                throttle.blocked_until = current_time + timedelta(
                    seconds=self.settings.root_login_block_seconds
                )
            self._audit(
                db_session,
                action="root.login_failed",
                request_id=request_id,
                source_key_hash=source_hash,
                now=current_time,
            )
            return LoginFailure(code="ROOT_TOKEN_INVALID")

        throttle.failure_count = 0
        throttle.window_started_at = current_time
        throttle.blocked_until = None
        throttle.updated_at = current_time

        session_token = random_opaque_token()
        csrf_token = random_opaque_token()
        root_session = Session(
            token_hash=self.session_token_hash(session_token),
            principal_type="root",
            auth_epoch=auth_epoch(self.admin_token),
            csrf_token_hash=self.csrf_token_hash(csrf_token),
            expires_at=current_time + timedelta(seconds=self.settings.root_session_ttl_seconds),
            last_seen_at=current_time,
            created_at=current_time,
        )
        db_session.add(root_session)
        await db_session.flush()
        self._audit(
            db_session,
            action="root.login_succeeded",
            request_id=request_id,
            source_key_hash=source_hash,
            entity_id=str(root_session.id),
            actor_id=str(root_session.id),
            now=current_time,
        )
        return LoginSuccess(
            session_token=session_token, csrf_token=csrf_token, session=root_session
        )

    async def authenticate(
        self,
        db_session: AsyncSession,
        token: str,
        *,
        now: datetime | None = None,
    ) -> Session | None:
        current_time = now or datetime.now(UTC)
        root_session = await db_session.scalar(
            select(Session).where(
                Session.token_hash == self.session_token_hash(token),
                Session.principal_type == "root",
            )
        )
        if root_session is None or root_session.revoked_at is not None:
            return None
        if root_session.expires_at <= current_time:
            root_session.revoked_at = current_time
            return None
        if not constant_time_token_matches(root_session.auth_epoch, auth_epoch(self.admin_token)):
            root_session.revoked_at = current_time
            return None
        # Sliding session: every authenticated request pushes the expiry forward so
        # an actively used panel stays logged in.
        root_session.last_seen_at = current_time
        root_session.expires_at = current_time + timedelta(
            seconds=self.settings.root_session_ttl_seconds
        )
        return root_session

    def csrf_matches(self, root_session: Session, csrf_token: str) -> bool:
        return constant_time_token_matches(
            root_session.csrf_token_hash,
            self.csrf_token_hash(csrf_token),
        )

    async def _locked_throttle(
        self,
        db_session: AsyncSession,
        source_hash: str,
        now: datetime,
    ) -> AuthThrottle:
        await db_session.execute(
            insert(AuthThrottle)
            .values(
                key_hash=source_hash,
                failure_count=0,
                window_started_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=[AuthThrottle.key_hash])
        )
        throttle = await db_session.scalar(
            select(AuthThrottle).where(AuthThrottle.key_hash == source_hash).with_for_update()
        )
        if throttle is None:  # pragma: no cover - protected by the insert/select transaction
            raise RuntimeError("Auth throttle yaratilmadi")
        return throttle

    @staticmethod
    def _audit(
        db_session: AsyncSession,
        *,
        action: str,
        request_id: str,
        source_key_hash: str,
        now: datetime,
        entity_id: str | None = None,
        actor_id: str | None = None,
    ) -> None:
        db_session.add(
            AuditEvent(
                actor_kind="root" if actor_id else "anonymous",
                actor_id=actor_id,
                action=action,
                entity_type="session",
                entity_id=entity_id,
                request_id=request_id,
                source_key_hash=source_key_hash,
                changes={},
                occurred_at=now,
            )
        )
