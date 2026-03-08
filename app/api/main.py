from fastapi import APIRouter

from app.api.routes import (
    admin_users,
    applications,
    audit_logs,
    beneficiaries,
    documents,
    facilitators,
    login,
    notifications,
    private,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(facilitators.router)
api_router.include_router(beneficiaries.router)
api_router.include_router(applications.router)
api_router.include_router(documents.router)
api_router.include_router(admin_users.router)
api_router.include_router(audit_logs.router)
api_router.include_router(notifications.router)
api_router.include_router(utils.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
