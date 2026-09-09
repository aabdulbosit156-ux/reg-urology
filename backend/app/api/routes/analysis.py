import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_db, require_roles, staff_id_or_none
from app.models.analysis import Analysis, AnalysisUploadedBy
from app.models.patient import Patient, PatientStatus
from app.models.staff import StaffRole
from app.schemas.analysis import AnalysisOut
from app.services import ai_analysis, telegram
from app.services.events import broadcast

router = APIRouter(tags=["analysis"])

STAFF_ROLES = (StaffRole.dev, StaffRole.director, StaffRole.admin, StaffRole.analyst)


@router.post(
    "/patients/{patient_id}/analysis",
    response_model=AnalysisOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_analysis(
    patient_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_roles(*STAFF_ROLES)),
) -> AnalysisOut:
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bemor topilmadi")
    if not patient.telegram_user_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Bemor hali botga ulanmagan, fayl yuborib bo'lmaydi"
        )

    content = await file.read()
    sent = await telegram.send_document(
        db,
        patient.telegram_user_id,
        content,
        file.filename or "analysis",
        file.content_type,
        caption="Analiz namunasi",
    )
    if sent is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Bot tokeni sozlanmagan")
    file_id, file_unique_id = sent

    analysis = Analysis(
        patient_id=patient.id,
        uploaded_by=AnalysisUploadedBy.staff,
        uploaded_by_staff_id=staff_id_or_none(principal),
        telegram_file_id=file_id,
        telegram_file_unique_id=file_unique_id,
        file_name=file.filename,
        mime_type=file.content_type,
        ordered=patient.status == PatientStatus.analysis_ordered,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    broadcast()
    return AnalysisOut.model_validate(analysis)


@router.get("/analysis/{analysis_id}/file")
async def get_analysis_file(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentPrincipal = Depends(require_roles(*STAFF_ROLES)),
) -> Response:
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fayl topilmadi")

    content = await telegram.download_file(db, analysis.telegram_file_id)
    if content is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Bot tokeni sozlanmagan")

    return Response(content=content, media_type=analysis.mime_type or "application/octet-stream")


@router.post("/analysis/{analysis_id}/ai-report", response_model=AnalysisOut)
async def generate_ai_report(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentPrincipal = Depends(require_roles(*STAFF_ROLES)),
) -> AnalysisOut:
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fayl topilmadi")

    try:
        report = await ai_analysis.analyze_lab_report(db, analysis)
    except ai_analysis.AIAnalysisError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    analysis.ai_report = report
    await db.commit()
    await db.refresh(analysis)

    patient_result = await db.execute(select(Patient).where(Patient.id == analysis.patient_id))
    patient = patient_result.scalar_one_or_none()
    if patient and patient.telegram_user_id:
        await telegram.send_text(db, patient.telegram_user_id, f"\U0001f4cb Analiz tahlili:\n\n{report}")

    return AnalysisOut.model_validate(analysis)
