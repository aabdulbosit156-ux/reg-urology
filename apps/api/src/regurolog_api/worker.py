import asyncio
import logging
import os
import signal
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from regurolog_api.config import Settings
from regurolog_api.database import Database
from regurolog_api.models import (
    Appointment,
    BotChatBinding,
    BotConnection,
    ContactAttempt,
    OutboxJob,
    RegistrationDraft,
    TelegramInbox,
    WorkerHeartbeat,
)
from regurolog_api.services.bot_connection import BotConnectionService
from regurolog_api.services.outbox import enqueue_telegram_message
from regurolog_api.services.registration import TelegramRegistrationService
from regurolog_api.services.templates import bot_messages

logger = logging.getLogger("regurolog.worker")
LEASE_SECONDS = 60
MAX_ATTEMPTS = 8


def _retry_at(attempts: int, now: datetime) -> datetime:
    delay = min(300, 2 ** min(attempts, 8))
    return now + timedelta(seconds=delay)


class Worker:
    def __init__(self, settings: Settings, database: Database) -> None:
        self.settings = settings
        self.database = database
        self.registration = TelegramRegistrationService(settings)
        self.bot_connections = BotConnectionService(settings)
        self.name = os.environ.get("RAILWAY_REPLICA_ID", "worker-local")[:64]

    async def tick(self) -> None:
        await self._heartbeat()
        await self._maintain_expired_work()
        await self._process_one_inbox()
        await self._process_one_outbox()

    async def _heartbeat(self) -> None:
        now = datetime.now(UTC)
        async with self.database.session_factory() as db_session:
            async with db_session.begin():
                await db_session.execute(
                    insert(WorkerHeartbeat)
                    .values(worker_name=self.name, last_seen_at=now, details={"state": "running"})
                    .on_conflict_do_update(
                        index_elements=[WorkerHeartbeat.worker_name],
                        set_={"last_seen_at": now, "details": {"state": "running"}},
                    )
                )

    async def _claim_inbox(self) -> UUID | None:
        now = datetime.now(UTC)
        async with self.database.session_factory() as db_session:
            async with db_session.begin():
                item = await db_session.scalar(
                    select(TelegramInbox)
                    .where(
                        or_(
                            and_(
                                TelegramInbox.state == "pending",
                                or_(
                                    TelegramInbox.lease_until.is_(None),
                                    TelegramInbox.lease_until <= now,
                                ),
                            ),
                            and_(
                                TelegramInbox.state == "processing",
                                TelegramInbox.lease_until <= now,
                            ),
                        )
                    )
                    .order_by(TelegramInbox.received_at)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                if item is None:
                    return None
                item.state = "processing"
                item.attempts += 1
                item.lease_until = now + timedelta(seconds=LEASE_SECONDS)
                return item.id

    async def _process_one_inbox(self) -> None:
        item_id = await self._claim_inbox()
        if item_id is None:
            return
        try:
            async with self.database.session_factory() as db_session:
                async with db_session.begin():
                    item = await db_session.scalar(
                        select(TelegramInbox)
                        .where(TelegramInbox.id == item_id, TelegramInbox.state == "processing")
                        .with_for_update()
                    )
                    if item is None:
                        return
                    await self.registration.process_update(
                        db_session,
                        bot_id=item.bot_id,
                        update_id=item.update_id,
                        payload=item.payload,
                    )
                    item.state = "completed"
                    item.completed_at = datetime.now(UTC)
                    item.lease_until = None
                    item.last_error = None
        except Exception as error:
            logger.exception("Telegram inbox processing failed; item_id=%s", item_id)
            await self._retry_inbox(item_id, type(error).__name__)

    async def _retry_inbox(self, item_id: UUID, error_name: str) -> None:
        now = datetime.now(UTC)
        async with self.database.session_factory() as db_session:
            async with db_session.begin():
                item = await db_session.get(TelegramInbox, item_id, with_for_update=True)
                if item is None:
                    return
                item.state = "failed" if item.attempts >= MAX_ATTEMPTS else "pending"
                item.lease_until = (
                    None if item.attempts >= MAX_ATTEMPTS else _retry_at(item.attempts, now)
                )
                item.last_error = error_name[:240]

    async def _claim_outbox(self) -> UUID | None:
        now = datetime.now(UTC)
        async with self.database.session_factory() as db_session:
            async with db_session.begin():
                job = await db_session.scalar(
                    select(OutboxJob)
                    .where(
                        OutboxJob.due_at <= now,
                        or_(
                            and_(
                                OutboxJob.state == "pending",
                                or_(OutboxJob.lease_until.is_(None), OutboxJob.lease_until <= now),
                            ),
                            and_(OutboxJob.state == "processing", OutboxJob.lease_until <= now),
                        ),
                    )
                    .order_by(OutboxJob.due_at, OutboxJob.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                if job is None:
                    return None
                job.state = "processing"
                job.attempts += 1
                job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
                return job.id

    async def _process_one_outbox(self) -> None:
        job_id = await self._claim_outbox()
        if job_id is None:
            return
        retry_after: int | None = None
        error_name: str | None = None
        blocked = False
        try:
            async with self.database.session_factory() as db_session:
                job = await db_session.get(OutboxJob, job_id)
                if job is None or job.state != "processing":
                    return
                if await self._is_stale_appointment_job(db_session, job):
                    job.state = "cancelled"
                    job.lease_until = None
                    await db_session.commit()
                    return
                connection = await db_session.scalar(
                    select(BotConnection).where(BotConnection.bot_id == job.bot_id)
                )
                if connection is None or job.chat_id is None:
                    raise RuntimeError("BotConnectionUnavailable")
                token = self.bot_connections.decrypt_token(connection)
                await self._send(token, job.chat_id, job.payload)
        except TelegramRetryAfter as error:
            retry_after = int(error.retry_after)
            error_name = type(error).__name__
        except TelegramForbiddenError as error:
            blocked = True
            error_name = type(error).__name__
        except Exception as error:
            logger.exception("Outbox delivery failed; job_id=%s", job_id)
            error_name = type(error).__name__
        await self._finish_outbox(job_id, error_name, retry_after, blocked)

    async def _is_stale_appointment_job(self, db_session: AsyncSession, job: OutboxJob) -> bool:
        if not job.kind.startswith("appointment_") or job.entity_id is None:
            return False
        appointment = await db_session.get(Appointment, job.entity_id)
        if appointment is None or appointment.version != job.version:
            return True
        if job.kind.startswith("appointment_reminder_"):
            return appointment.status != "scheduled" or appointment.start_at <= datetime.now(UTC)
        return False

    async def _send(self, token: str, chat_id: int, payload: dict[str, Any]) -> None:
        bot = Bot(token=token)
        try:
            markup_data = payload.get("reply_markup")
            markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None
            if isinstance(markup_data, dict):
                if "inline_keyboard" in markup_data:
                    markup = InlineKeyboardMarkup.model_validate(markup_data)
                elif "keyboard" in markup_data:
                    markup = ReplyKeyboardMarkup.model_validate(markup_data)
            await bot.send_message(
                chat_id=chat_id,
                text=str(payload.get("text") or ""),
                reply_markup=markup,
            )
        finally:
            await bot.session.close()

    async def _finish_outbox(
        self,
        job_id: UUID,
        error_name: str | None,
        retry_after: int | None,
        blocked: bool,
    ) -> None:
        now = datetime.now(UTC)
        async with self.database.session_factory() as db_session:
            async with db_session.begin():
                job = await db_session.get(OutboxJob, job_id, with_for_update=True)
                if job is None:
                    return
                if error_name is None:
                    job.state = "sent"
                    job.sent_at = now
                    job.lease_until = None
                    job.last_error = None
                    return
                job.last_error = error_name[:240]
                terminal = blocked or job.attempts >= MAX_ATTEMPTS
                job.state = "failed" if terminal else "pending"
                job.lease_until = None
                job.due_at = now + timedelta(seconds=retry_after or min(300, 2**job.attempts))
                if blocked and job.bot_id is not None and job.chat_id is not None:
                    await db_session.execute(
                        update(BotChatBinding)
                        .where(
                            BotChatBinding.bot_id == job.bot_id,
                            BotChatBinding.chat_id == job.chat_id,
                        )
                        .values(reachable=False)
                    )

    async def _maintain_expired_work(self) -> None:
        now = datetime.now(UTC)
        inbox_payload_cutoff = now - timedelta(hours=self.settings.inbox_payload_retention_hours)
        async with self.database.session_factory() as db_session:
            async with db_session.begin():
                # Keep the deduplication row and technical metadata, but remove raw
                # Telegram content after the configured short retention window.
                await db_session.execute(
                    update(TelegramInbox)
                    .where(
                        TelegramInbox.payload != {},
                        or_(
                            and_(
                                TelegramInbox.state == "completed",
                                TelegramInbox.completed_at <= inbox_payload_cutoff,
                            ),
                            and_(
                                TelegramInbox.state == "failed",
                                TelegramInbox.received_at <= inbox_payload_cutoff,
                            ),
                        ),
                    )
                    .values(payload={})
                )
                attempts = list(
                    (
                        await db_session.scalars(
                            select(ContactAttempt)
                            .where(
                                ContactAttempt.outcome == "in_progress",
                                ContactAttempt.lease_until <= now,
                            )
                            .with_for_update(skip_locked=True)
                            .limit(20)
                        )
                    ).all()
                )
                for attempt in attempts:
                    attempt.outcome = "interrupted"
                    attempt.ended_at = now

                drafts = list(
                    (
                        await db_session.scalars(
                            select(RegistrationDraft)
                            .where(
                                RegistrationDraft.expires_at <= now,
                                RegistrationDraft.step.notin_(["FINISHED", "EXPIRED", "CANCELLED"]),
                            )
                            .with_for_update(skip_locked=True)
                            .limit(20)
                        )
                    ).all()
                )
                for draft in drafts:
                    if draft.step == "OPTIONAL_REASON":
                        messages, _ = await bot_messages(db_session, draft.template_version)
                        await enqueue_telegram_message(
                            db_session,
                            idempotency_key=f"draft:{draft.id}:timeout-finished",
                            bot_id=draft.bot_id,
                            chat_id=draft.chat_id,
                            text=messages["finished"],
                        )
                        draft.step = "FINISHED"
                    else:
                        draft.step = "EXPIRED"
                    draft.data = {}
                    draft.updated_at = now


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL worker uchun majburiy")
    database = Database(settings.database_url)
    worker = Worker(settings, database)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(shutdown_signal, stop_event.set)
        except NotImplementedError:
            # Windows local smoke runs do not implement loop signal handlers.
            pass
    try:
        while not stop_event.is_set():
            await worker.tick()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=settings.worker_poll_seconds)
            except TimeoutError:
                pass
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(run())
