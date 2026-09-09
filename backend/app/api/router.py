from fastapi import APIRouter

from app.api.routes import analysis, appointments, auth, health, patients, settings

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(analysis.router)
api_router.include_router(appointments.router)
api_router.include_router(settings.router)
