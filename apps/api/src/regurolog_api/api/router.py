from fastapi import APIRouter

from regurolog_api.api.routes.auth import router as auth_router
from regurolog_api.api.routes.bot import router as bot_router
from regurolog_api.api.routes.calendar import router as calendar_router
from regurolog_api.api.routes.crm import router as crm_router
from regurolog_api.api.routes.health import router as health_router
from regurolog_api.api.routes.management import router as management_router
from regurolog_api.api.routes.staff import router as staff_router
from regurolog_api.api.routes.telegram import router as telegram_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(bot_router, prefix="/bot-connection", tags=["bot"])
api_router.include_router(calendar_router, tags=["calendar"])
api_router.include_router(crm_router, tags=["crm"])
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(management_router, tags=["management"])
api_router.include_router(staff_router, prefix="/staff", tags=["staff"])
api_router.include_router(telegram_router, prefix="/telegram", tags=["telegram"])
