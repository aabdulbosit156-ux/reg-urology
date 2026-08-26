import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from regurolog_api.database import Database
from regurolog_api.models import Appointment, Doctor, Inquiry, Patient, ReceptionSheet
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parallel_appointment_insert_allows_only_one_slot_owner() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL berilmagan")
    database = Database(database_url)
    marker = uuid4().hex[:10]
    now = datetime.now(UTC)
    start_at = (now + timedelta(days=7)).replace(minute=0, second=0, microsecond=0)
    doctor_id = uuid4()
    inquiry_ids = [uuid4(), uuid4()]
    sheet_ids = [uuid4(), uuid4()]
    patient_ids = [uuid4(), uuid4()]
    try:
        async with database.session_factory() as db_session:
            async with db_session.begin():
                db_session.add(
                    Doctor(
                        id=doctor_id,
                        name=f"Constraint doctor {marker}",
                        timezone="Asia/Tashkent",
                        active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
                for index in range(2):
                    db_session.add(
                        Patient(
                            id=patient_ids[index],
                            telegram_user_id=-(int(marker[:6], 16) * 10 + index + 1),
                            full_name=f"Test Patient {index}",
                            phone_e164=f"+99899000{index:04d}",
                            phone_source="manual",
                            phone_verified=False,
                            possible_duplicate=False,
                            first_registered_at=now,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    db_session.add(
                        Inquiry(
                            id=inquiry_ids[index],
                            patient_id=patient_ids[index],
                            doctor_id=doctor_id,
                            status="open",
                            contact_snapshot={},
                            source_snapshot={"kind": "test"},
                            registered_at=now,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    db_session.add(
                        ReceptionSheet(
                            id=sheet_ids[index],
                            inquiry_id=inquiry_ids[index],
                            local_contact_date=now.date(),
                            number=f"RU-TEST-{marker}-{index}",
                            contact_snapshot={},
                            created_at=now,
                            updated_at=now,
                        )
                    )

        async def insert_appointment(index: int) -> bool:
            try:
                async with database.session_factory() as db_session:
                    async with db_session.begin():
                        db_session.add(
                            Appointment(
                                inquiry_id=inquiry_ids[index],
                                doctor_id=doctor_id,
                                sheet_id=sheet_ids[index],
                                start_at=start_at,
                                end_at=start_at + timedelta(minutes=15),
                                status="scheduled",
                                schedule_version=1,
                                version=1,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                return True
            except IntegrityError:
                return False

        results = await asyncio.gather(insert_appointment(0), insert_appointment(1))
        assert sorted(results) == [False, True]
    finally:
        async with database.session_factory() as db_session:
            async with db_session.begin():
                await db_session.execute(
                    delete(Appointment).where(Appointment.doctor_id == doctor_id)
                )
                await db_session.execute(
                    delete(ReceptionSheet).where(ReceptionSheet.id.in_(sheet_ids))
                )
                await db_session.execute(delete(Inquiry).where(Inquiry.id.in_(inquiry_ids)))
                await db_session.execute(delete(Patient).where(Patient.id.in_(patient_ids)))
                await db_session.execute(delete(Doctor).where(Doctor.id == doctor_id))
        await database.close()
