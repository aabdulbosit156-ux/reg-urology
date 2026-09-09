from fastapi import APIRouter

from app.api.routes import (
    activity,
    analysis,
    appointments,
    auth,
    dashboard,
    events,
    health,
    patients,
    settings,
    staff,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(analysis.router)
api_router.include_router(appointments.router)
api_router.include_router(settings.router)
api_router.include_router(dashboard.router)
api_router.include_router(staff.router)
api_router.include_router(activity.router)
api_router.include_router(events.router)
