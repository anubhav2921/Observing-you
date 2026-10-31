"""
backend/app/api/routes — REST API routers.
"""

from fastapi import APIRouter
from backend.app.api.routes.system import router as system_router
from backend.app.api.routes.session import router as session_router

api_router = APIRouter(prefix="/api")
api_router.include_router(system_router)
api_router.include_router(session_router)

__all__ = ["api_router"]

