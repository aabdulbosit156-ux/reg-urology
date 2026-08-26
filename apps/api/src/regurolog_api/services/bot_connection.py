from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from regurolog_api.config import Settings
from regurolog_api.crypto import TokenCipher
from regurolog_api.models import BotConnection
from regurolog_api.security import keyed_digest, random_opaque_token


class BotConnectionError(RuntimeError):
    pass


class BotReplacementRequired(BotConnectionError):
    pass


@dataclass(frozen=True, slots=True)
class BotIdentity:
    bot_id: int
    username: str
    display_name: str


@dataclass(frozen=True, slots=True)
class BotConnectOutcome:
    connection: BotConnection
    replaced_connection_id: UUID | None = None
    replaced_token: str | None = None


class TelegramBotGateway:
    async def identity(self, token: str) -> BotIdentity:
        bot = Bot(token=token)
        try:
            me = await bot.get_me()
            if not me.username:
                raise BotConnectionError("Bot username topilmadi")
            return BotIdentity(bot_id=me.id, username=me.username, display_name=me.full_name)
        except TelegramAPIError as error:
            raise BotConnectionError("Telegram bot tokenini tasdiqlamadi") from error
        finally:
            await bot.session.close()

    async def set_webhook(self, token: str, url: str, secret_token: str) -> None:
        bot = Bot(token=token)
        try:
            accepted = await bot.set_webhook(
                url=url,
                secret_token=secret_token,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=False,
            )
            if not accepted:
                raise BotConnectionError("Telegram webhookni qabul qilmadi")
        except TelegramAPIError as error:
            raise BotConnectionError("Telegram webhookini o‘rnatib bo‘lmadi") from error
        finally:
            await bot.session.close()

    async def delete_webhook(self, token: str) -> None:
        bot = Bot(token=token)
        try:
            accepted = await bot.delete_webhook(drop_pending_updates=False)
            if not accepted:
                raise BotConnectionError("Eski Telegram webhook o‘chirilmadi")
        except TelegramAPIError as error:
            raise BotConnectionError("Eski Telegram webhookni o‘chirib bo‘lmadi") from error
        finally:
            await bot.session.close()


class BotConnectionService:
    def __init__(self, settings: Settings, gateway: TelegramBotGateway | None = None) -> None:
        if settings.app_encryption_key is None or settings.webhook_secret is None:
            raise RuntimeError("Bot uchun encryption/webhook secret sozlanmagan")
        self.settings = settings
        self.gateway = gateway or TelegramBotGateway()
        self.cipher = TokenCipher(settings.app_encryption_key.get_secret_value())
        self.webhook_secret = settings.webhook_secret.get_secret_value()

    def webhook_path_hash(self, path: str) -> str:
        return keyed_digest(f"webhook-path:{path}", self.webhook_secret)

    def telegram_webhook_secret(self, path: str) -> str:
        return keyed_digest(f"telegram-secret:{path}", self.webhook_secret)

    async def validate(self, token: str) -> BotIdentity:
        return await self.gateway.identity(token)

    async def connect(
        self,
        db_session: AsyncSession,
        *,
        token: str,
        confirm_replace: bool,
        now: datetime | None = None,
    ) -> BotConnectOutcome:
        current_time = now or datetime.now(UTC)
        if not self.settings.public_base_url:
            raise BotConnectionError("PUBLIC_BASE_URL sozlanmagan")
        identity = await self.gateway.identity(token)
        active = await db_session.scalar(
            select(BotConnection).where(BotConnection.active.is_(True)).with_for_update()
        )
        if active and active.bot_id != identity.bot_id and not confirm_replace:
            raise BotReplacementRequired("Boshqa botga o‘tish uchun maxsus tasdiq kerak")

        webhook_path = random_opaque_token()
        telegram_secret = self.telegram_webhook_secret(webhook_path)
        webhook_url = (
            f"{self.settings.public_base_url.rstrip('/')}/api/v1/telegram/webhook/{webhook_path}"
        )
        await self.gateway.set_webhook(token, webhook_url, telegram_secret)

        if active and active.bot_id == identity.bot_id:
            active.username = identity.username
            active.display_name = identity.display_name
            active.encrypted_token = self.cipher.encrypt(token)
            active.webhook_path_hash = self.webhook_path_hash(webhook_path)
            active.webhook_secret_hash = keyed_digest(
                "header:" + telegram_secret, self.webhook_secret
            )
            active.config_version += 1
            active.status = "connected"
            active.last_error = None
            active.updated_at = current_time
            return BotConnectOutcome(connection=active)

        replaced_connection_id: UUID | None = None
        replaced_token: str | None = None
        if active:
            replaced_connection_id = active.id
            try:
                replaced_token = self.decrypt_token(active)
            except ValueError:
                # A rotated encryption key must not prevent a valid new bot from
                # taking over. The old endpoint becomes inactive and returns 404.
                active.last_error = "OLD_WEBHOOK_CLEANUP_FAILED"
            active.active = False
            active.status = "error" if replaced_token is None else "reconnect_required"
            active.updated_at = current_time

        connection = BotConnection(
            bot_id=identity.bot_id,
            username=identity.username,
            display_name=identity.display_name,
            encrypted_token=self.cipher.encrypt(token),
            webhook_path_hash=self.webhook_path_hash(webhook_path),
            webhook_secret_hash=keyed_digest("header:" + telegram_secret, self.webhook_secret),
            config_version=1,
            status="connected",
            active=True,
            created_at=current_time,
            updated_at=current_time,
        )
        db_session.add(connection)
        await db_session.flush()
        return BotConnectOutcome(
            connection=connection,
            replaced_connection_id=replaced_connection_id,
            replaced_token=replaced_token,
        )

    async def active_connection(self, db_session: AsyncSession) -> BotConnection | None:
        connection = await db_session.scalar(
            select(BotConnection).where(BotConnection.active.is_(True))
        )
        return connection

    def decrypt_token(self, connection: BotConnection) -> str:
        return self.cipher.decrypt(connection.encrypted_token)
