from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from regurolog_api.config import Settings
from regurolog_api.domain.validation import (
    DomainValidationError,
    normalize_full_name,
    normalize_uz_phone,
)
from regurolog_api.models import (
    AttributionEvent,
    BotChatBinding,
    Campaign,
    Consent,
    Doctor,
    Inquiry,
    Patient,
    RegistrationDraft,
    StaffUser,
)
from regurolog_api.services.outbox import enqueue_telegram_message
from regurolog_api.services.staff import StaffService
from regurolog_api.services.staff_auth import StaffAuthService
from regurolog_api.services.templates import bot_messages


def inline_button(label: str, callback_data: str) -> dict[str, object]:
    return {"inline_keyboard": [[{"text": label, "callback_data": callback_data}]]}


def source_snapshot(campaign: Campaign | None, kind: str) -> dict[str, Any]:
    if campaign is None:
        return {"kind": kind}
    return {
        "kind": kind,
        "campaign_id": str(campaign.id),
        "code": campaign.code,
        "name": campaign.name,
        "utm_source": campaign.utm_source,
        "utm_medium": campaign.utm_medium,
        "utm_campaign": campaign.utm_campaign,
        "utm_content": campaign.utm_content,
        "utm_term": campaign.utm_term,
    }


class TelegramRegistrationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def process_update(
        self,
        db_session: AsyncSession,
        *,
        bot_id: int,
        update_id: int,
        payload: dict[str, Any],
    ) -> None:
        message = payload.get("message")
        callback = payload.get("callback_query")
        source = message if isinstance(message, dict) else callback
        if not isinstance(source, dict):
            return
        user = source.get("from")
        if not isinstance(user, dict) or not isinstance(user.get("id"), int):
            return
        telegram_user_id = int(user["id"])
        if message:
            chat = message.get("chat", {})
        else:
            callback_message = callback.get("message") if isinstance(callback, dict) else None
            chat = callback_message.get("chat", {}) if isinstance(callback_message, dict) else {}
        if not isinstance(chat, dict) or chat.get("type") != "private":
            return
        chat_id = int(chat["id"])
        await self._touch_binding(db_session, bot_id, telegram_user_id, chat_id)

        if message:
            await self._process_message(
                db_session,
                bot_id=bot_id,
                update_id=update_id,
                message=message,
                user=user,
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
            )
        elif callback:
            await self._process_callback(
                db_session,
                bot_id=bot_id,
                update_id=update_id,
                callback=callback,
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
            )

    async def _touch_binding(
        self, db_session: AsyncSession, bot_id: int, telegram_user_id: int, chat_id: int
    ) -> None:
        now = datetime.now(UTC)
        await db_session.execute(
            insert(BotChatBinding)
            .values(
                bot_id=bot_id,
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                reachable=True,
                last_seen_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_bot_chat_bindings_bot_user",
                set_={"chat_id": chat_id, "reachable": True, "last_seen_at": now},
            )
        )

    async def _process_message(
        self,
        db_session: AsyncSession,
        *,
        bot_id: int,
        update_id: int,
        message: dict[str, Any],
        user: dict[str, Any],
        telegram_user_id: int,
        chat_id: int,
    ) -> None:
        text = str(message.get("text") or "").strip()
        if text.startswith("/start"):
            parameter = text.partition(" ")[2].strip()
            if parameter.startswith("invite_"):
                await self._claim_invite(
                    db_session,
                    token=parameter.removeprefix("invite_"),
                    user=user,
                    bot_id=bot_id,
                    chat_id=chat_id,
                    update_id=update_id,
                )
                return
            if parameter.startswith("login_"):
                await self._claim_login(
                    db_session,
                    token=parameter.removeprefix("login_"),
                    telegram_user_id=telegram_user_id,
                    bot_id=bot_id,
                    chat_id=chat_id,
                    update_id=update_id,
                )
                return
            source_code = parameter.removeprefix("src_") if parameter.startswith("src_") else None
            await self._start_patient(
                db_session,
                bot_id=bot_id,
                update_id=update_id,
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                source_code=source_code,
            )
            return

        draft = await db_session.scalar(
            select(RegistrationDraft).where(
                RegistrationDraft.bot_id == bot_id,
                RegistrationDraft.telegram_user_id == telegram_user_id,
            )
        )
        if text == "/cancel":
            if draft:
                draft.step = "CANCELLED"
                draft.data = {}
                draft.expires_at = datetime.now(UTC)
            return
        if draft is None:
            return
        messages, _ = await bot_messages(db_session, draft.template_version)
        if draft.step == "WAIT_FULL_NAME":
            try:
                full_name = normalize_full_name(text)
            except DomainValidationError as error:
                await enqueue_telegram_message(
                    db_session,
                    idempotency_key=f"update:{bot_id}:{update_id}:name-error",
                    bot_id=bot_id,
                    chat_id=chat_id,
                    text=error.message,
                )
                return
            draft.data = {**draft.data, "full_name": full_name}
            draft.step = "WAIT_PHONE"
            draft.updated_at = datetime.now(UTC)
            await enqueue_telegram_message(
                db_session,
                idempotency_key=f"update:{bot_id}:{update_id}:phone-prompt",
                bot_id=bot_id,
                chat_id=chat_id,
                text=messages["phone_prompt"],
                reply_markup={
                    "keyboard": [[{"text": "Telefon raqamimni yuborish", "request_contact": True}]],
                    "resize_keyboard": True,
                    "one_time_keyboard": True,
                },
            )
            return
        if draft.step == "WAIT_PHONE":
            contact = message.get("contact")
            phone_source = "manual"
            phone_value = text
            verified = False
            if isinstance(contact, dict):
                if contact.get("user_id") != telegram_user_id:
                    await enqueue_telegram_message(
                        db_session,
                        idempotency_key=f"update:{bot_id}:{update_id}:foreign-contact",
                        bot_id=bot_id,
                        chat_id=chat_id,
                        text="Faqat o‘zingizning Telegram kontaktingizni yuboring.",
                    )
                    return
                phone_value = str(contact.get("phone_number") or "")
                phone_source = "telegram_contact"
                verified = True
            try:
                phone_e164 = normalize_uz_phone(phone_value)
            except DomainValidationError:
                await enqueue_telegram_message(
                    db_session,
                    idempotency_key=f"update:{bot_id}:{update_id}:phone-error",
                    bot_id=bot_id,
                    chat_id=chat_id,
                    text=messages["phone_error"],
                )
                return
            await self._commit_registration(
                db_session,
                draft=draft,
                update_id=update_id,
                full_name=str(draft.data["full_name"]),
                phone_e164=phone_e164,
                phone_source=phone_source,
                verified=verified,
            )
            return
        if draft.step == "OPTIONAL_REASON":
            inquiry_id = draft.data.get("inquiry_id")
            if inquiry_id and text and text != "Shart emas":
                if len(text) > 1000:
                    await enqueue_telegram_message(
                        db_session,
                        idempotency_key=f"update:{bot_id}:{update_id}:reason-error",
                        bot_id=bot_id,
                        chat_id=chat_id,
                        text="Izoh 1000 belgidan oshmasligi kerak.",
                    )
                    return
                inquiry = await db_session.get(Inquiry, UUID(str(inquiry_id)))
                if inquiry:
                    inquiry.reason = text
                    inquiry.version += 1
                    inquiry.updated_at = datetime.now(UTC)
            await self._finish_reason_step(db_session, draft, update_id, messages)

    async def _process_callback(
        self,
        db_session: AsyncSession,
        *,
        bot_id: int,
        update_id: int,
        callback: dict[str, Any],
        telegram_user_id: int,
        chat_id: int,
    ) -> None:
        data = str(callback.get("data") or "")
        if data.startswith("login_approve:") or data.startswith("login_reject:"):
            approved = data.startswith("login_approve:")
            challenge_id = data.partition(":")[2]
            accepted = await StaffAuthService(self.settings).confirm_from_telegram(
                db_session,
                challenge_id=challenge_id,
                telegram_user_id=telegram_user_id,
                approved=approved,
            )
            await enqueue_telegram_message(
                db_session,
                idempotency_key=f"update:{bot_id}:{update_id}:login-result",
                bot_id=bot_id,
                chat_id=chat_id,
                text=(
                    "Panelga kirish tasdiqlandi. Brauzerga qayting."
                    if accepted and approved
                    else "Kirish so‘rovi rad etildi yoki eskirgan."
                ),
            )
            return
        draft = await db_session.scalar(
            select(RegistrationDraft).where(
                RegistrationDraft.bot_id == bot_id,
                RegistrationDraft.telegram_user_id == telegram_user_id,
            )
        )
        if draft is None:
            return
        messages, _ = await bot_messages(db_session, draft.template_version)
        if data == "consent_accept" and draft.step == "CONSENT":
            draft.step = "WAIT_FULL_NAME"
            draft.data = {**draft.data, "consent_accepted_at": datetime.now(UTC).isoformat()}
            draft.updated_at = datetime.now(UTC)
            await enqueue_telegram_message(
                db_session,
                idempotency_key=f"update:{bot_id}:{update_id}:name-prompt",
                bot_id=bot_id,
                chat_id=chat_id,
                text=messages["full_name_prompt"],
            )
        elif data == "new_inquiry_confirm" and draft.step == "CONFIRM_NEW":
            patient = await db_session.get(Patient, UUID(str(draft.data["patient_id"])))
            if patient:
                await self._create_repeat_inquiry(db_session, draft, patient, update_id)
        elif data == "reason_skip" and draft.step == "OPTIONAL_REASON":
            await self._finish_reason_step(db_session, draft, update_id, messages)

    async def _finish_reason_step(
        self,
        db_session: AsyncSession,
        draft: RegistrationDraft,
        update_id: int,
        messages: dict[str, str],
    ) -> None:
        draft.step = "FINISHED"
        draft.data = {}
        draft.updated_at = datetime.now(UTC)
        await enqueue_telegram_message(
            db_session,
            idempotency_key=f"update:{draft.bot_id}:{update_id}:finished",
            bot_id=draft.bot_id,
            chat_id=draft.chat_id,
            text=messages["finished"],
        )

    async def _claim_invite(
        self,
        db_session: AsyncSession,
        *,
        token: str,
        user: dict[str, Any],
        bot_id: int,
        chat_id: int,
        update_id: int,
    ) -> None:
        full_name_raw = " ".join(
            part
            for part in [str(user.get("first_name") or ""), str(user.get("last_name") or "")]
            if part
        )
        try:
            full_name = normalize_full_name(full_name_raw)
        except DomainValidationError:
            full_name = full_name_raw.strip()[:120] or "Telegram foydalanuvchi"
        claimed = await StaffService(self.settings).claim_invite(
            db_session,
            token=token,
            telegram_user_id=int(user["id"]),
            full_name=full_name,
            username=str(user.get("username")) if user.get("username") else None,
        )
        await enqueue_telegram_message(
            db_session,
            idempotency_key=f"update:{bot_id}:{update_id}:invite",
            bot_id=bot_id,
            chat_id=chat_id,
            text=(
                "Taklif qabul qilindi. Paneldagi tasdiqni kuting."
                if claimed
                else "Taklif ishlatilgan, bekor qilingan yoki muddati tugagan."
            ),
        )

    async def _claim_login(
        self,
        db_session: AsyncSession,
        *,
        token: str,
        telegram_user_id: int,
        bot_id: int,
        chat_id: int,
        update_id: int,
    ) -> None:
        challenge = await StaffAuthService(self.settings).claim_from_telegram(
            db_session, login_token=token, telegram_user_id=telegram_user_id
        )
        if challenge is None:
            await enqueue_telegram_message(
                db_session,
                idempotency_key=f"update:{bot_id}:{update_id}:login-invalid",
                bot_id=bot_id,
                chat_id=chat_id,
                text="Kirish so‘rovi eskirgan yoki bu hisob active xodim emas.",
            )
            return
        markup: dict[str, object] = {
            "inline_keyboard": [
                [
                    {
                        "text": "Tasdiqlayman",
                        "callback_data": f"login_approve:{challenge.id}",
                    },
                    {
                        "text": "Men boshlamaganman",
                        "callback_data": f"login_reject:{challenge.id}",
                    },
                ]
            ]
        }
        await enqueue_telegram_message(
            db_session,
            idempotency_key=f"update:{bot_id}:{update_id}:login-confirm",
            bot_id=bot_id,
            chat_id=chat_id,
            text=f"Panelga kirishni tasdiqlaysizmi? Moslashtirish kodi: {challenge.matching_code}",
            reply_markup=markup,
        )

    async def _start_patient(
        self,
        db_session: AsyncSession,
        *,
        bot_id: int,
        update_id: int,
        telegram_user_id: int,
        chat_id: int,
        source_code: str | None,
    ) -> None:
        now = datetime.now(UTC)
        campaign = None
        kind = "organic"
        if source_code:
            campaign = await db_session.scalar(select(Campaign).where(Campaign.code == source_code))
            kind = (
                "unknown"
                if campaign is None
                else ("revoked" if campaign.revoked_at else "campaign")
            )
        db_session.add(
            AttributionEvent(
                bot_id=bot_id,
                telegram_user_id=telegram_user_id,
                campaign_id=campaign.id if campaign else None,
                source_kind=kind,
                event_type="start",
                occurred_at=now,
            )
        )
        patient = await db_session.scalar(
            select(Patient).where(Patient.telegram_user_id == telegram_user_id)
        )
        messages, template_version = await bot_messages(db_session)
        if patient:
            patient.last_touch_source_id = campaign.id if campaign else patient.last_touch_source_id
            patient.updated_at = now
            open_inquiry = await db_session.scalar(
                select(Inquiry).where(Inquiry.patient_id == patient.id, Inquiry.status == "open")
            )
            if open_inquiry:
                await enqueue_telegram_message(
                    db_session,
                    idempotency_key=f"update:{bot_id}:{update_id}:already",
                    bot_id=bot_id,
                    chat_id=chat_id,
                    text=messages["already_registered"],
                )
                return
        draft = await db_session.scalar(
            select(RegistrationDraft)
            .where(
                RegistrationDraft.bot_id == bot_id,
                RegistrationDraft.telegram_user_id == telegram_user_id,
            )
            .with_for_update()
        )
        if draft is None:
            draft = RegistrationDraft(
                bot_id=bot_id,
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                step="WAIT_FULL_NAME",
                data={},
                attribution_id=campaign.id if campaign else None,
                attribution_kind=kind,
                template_version=template_version,
                expires_at=now + timedelta(hours=24),
                created_at=now,
                updated_at=now,
            )
            db_session.add(draft)
        else:
            draft.chat_id = chat_id
            if draft.step in {"FINISHED", "EXPIRED", "CANCELLED"}:
                draft.attribution_id = campaign.id if campaign else None
                draft.attribution_kind = kind
                draft.template_version = template_version
            draft.expires_at = now + timedelta(hours=24)
            draft.updated_at = now
        if patient:
            draft.step = "CONFIRM_NEW"
            draft.data = {"patient_id": str(patient.id)}
            await enqueue_telegram_message(
                db_session,
                idempotency_key=f"update:{bot_id}:{update_id}:repeat-confirm",
                bot_id=bot_id,
                chat_id=chat_id,
                text=messages["new_inquiry_confirm"],
                reply_markup=inline_button("Yangi murojaat ochish", "new_inquiry_confirm"),
            )
            return
        draft.step = "WAIT_FULL_NAME"
        await enqueue_telegram_message(
            db_session,
            idempotency_key=f"update:{bot_id}:{update_id}:name-prompt",
            bot_id=bot_id,
            chat_id=chat_id,
            text=messages["full_name_prompt"],
        )

    async def _commit_registration(
        self,
        db_session: AsyncSession,
        *,
        draft: RegistrationDraft,
        update_id: int,
        full_name: str,
        phone_e164: str,
        phone_source: str,
        verified: bool,
    ) -> None:
        now = datetime.now(UTC)
        doctor = await db_session.scalar(select(Doctor).where(Doctor.active.is_(True)))
        messages, _ = await bot_messages(db_session, draft.template_version)
        if doctor is None:
            await enqueue_telegram_message(
                db_session,
                idempotency_key=f"update:{draft.bot_id}:{update_id}:clinic-missing",
                bot_id=draft.bot_id,
                chat_id=draft.chat_id,
                text=messages["generic_error"],
            )
            return
        duplicates = list(
            (
                await db_session.scalars(
                    select(Patient).where(
                        Patient.phone_e164 == phone_e164,
                        Patient.telegram_user_id != draft.telegram_user_id,
                    )
                )
            ).all()
        )
        for existing_patient in duplicates:
            existing_patient.possible_duplicate = True
            existing_patient.updated_at = now
        patient = Patient(
            telegram_user_id=draft.telegram_user_id,
            full_name=full_name,
            phone_e164=phone_e164,
            phone_source=phone_source,
            phone_verified=verified,
            possible_duplicate=bool(duplicates),
            first_source_id=draft.attribution_id,
            last_touch_source_id=draft.attribution_id,
            first_registered_at=now,
            created_at=now,
            updated_at=now,
        )
        db_session.add(patient)
        await db_session.flush()
        inquiry = Inquiry(
            patient_id=patient.id,
            doctor_id=doctor.id,
            status="open",
            contact_snapshot={"full_name": full_name, "phone_e164": phone_e164},
            source_snapshot=source_snapshot(
                await db_session.get(Campaign, draft.attribution_id)
                if draft.attribution_id
                else None,
                draft.attribution_kind,
            ),
            registered_at=now,
            created_at=now,
            updated_at=now,
        )
        db_session.add(inquiry)
        await db_session.flush()
        db_session.add(
            Consent(
                patient_id=patient.id,
                draft_id=draft.id,
                version=draft.template_version,
                purpose="contact_and_appointment",
                accepted_at=now,
            )
        )
        db_session.add(
            AttributionEvent(
                bot_id=draft.bot_id,
                telegram_user_id=draft.telegram_user_id,
                campaign_id=draft.attribution_id,
                source_kind=draft.attribution_kind,
                event_type="registered",
                occurred_at=now,
            )
        )
        draft.step = "OPTIONAL_REASON"
        draft.data = {"patient_id": str(patient.id), "inquiry_id": str(inquiry.id)}
        draft.updated_at = now
        await self._queue_registration_messages(db_session, draft, inquiry, update_id, messages)

    async def _create_repeat_inquiry(
        self,
        db_session: AsyncSession,
        draft: RegistrationDraft,
        patient: Patient,
        update_id: int,
    ) -> None:
        now = datetime.now(UTC)
        doctor = await db_session.scalar(select(Doctor).where(Doctor.active.is_(True)))
        if doctor is None:
            return
        inquiry = Inquiry(
            patient_id=patient.id,
            doctor_id=doctor.id,
            status="open",
            contact_snapshot={"full_name": patient.full_name, "phone_e164": patient.phone_e164},
            source_snapshot=source_snapshot(
                await db_session.get(Campaign, draft.attribution_id)
                if draft.attribution_id
                else None,
                draft.attribution_kind,
            ),
            registered_at=now,
            created_at=now,
            updated_at=now,
        )
        db_session.add(inquiry)
        await db_session.flush()
        patient.last_touch_source_id = draft.attribution_id
        db_session.add(
            AttributionEvent(
                bot_id=draft.bot_id,
                telegram_user_id=draft.telegram_user_id,
                campaign_id=draft.attribution_id,
                source_kind=draft.attribution_kind,
                event_type="registered",
                occurred_at=now,
            )
        )
        draft.step = "OPTIONAL_REASON"
        draft.data = {"patient_id": str(patient.id), "inquiry_id": str(inquiry.id)}
        messages, _ = await bot_messages(db_session, draft.template_version)
        await self._queue_registration_messages(db_session, draft, inquiry, update_id, messages)

    async def _queue_registration_messages(
        self,
        db_session: AsyncSession,
        draft: RegistrationDraft,
        inquiry: Inquiry,
        update_id: int,
        messages: dict[str, str],
    ) -> None:
        await enqueue_telegram_message(
            db_session,
            idempotency_key=f"update:{draft.bot_id}:{update_id}:reason-prompt",
            bot_id=draft.bot_id,
            chat_id=draft.chat_id,
            text=f"{messages['registered']} {messages['reason_prompt']}",
            reply_markup=inline_button("Shart emas", "reason_skip"),
            entity_id=inquiry.id,
        )
        active_staff = list(
            (
                await db_session.scalars(
                    select(BotChatBinding.chat_id)
                    .join(
                        StaffUser,
                        StaffUser.telegram_user_id == BotChatBinding.telegram_user_id,
                    )
                    .where(
                        BotChatBinding.bot_id == draft.bot_id,
                        BotChatBinding.reachable.is_(True),
                        StaffUser.state == "active",
                    )
                )
            ).all()
        )
        for staff_chat_id in active_staff:
            await enqueue_telegram_message(
                db_session,
                idempotency_key=f"inquiry:{inquiry.id}:new:{staff_chat_id}",
                bot_id=draft.bot_id,
                chat_id=staff_chat_id,
                text=f"Yangi murojaat #{str(inquiry.id)[:8]}",
                entity_id=inquiry.id,
                kind="staff_new_inquiry",
            )
