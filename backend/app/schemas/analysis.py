import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.analysis import AnalysisUploadedBy


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    uploaded_by: AnalysisUploadedBy
    file_name: str | None
    mime_type: str | None
    ordered: bool
    ai_report: str | None
    created_at: datetime
