"""Main API router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.folders import router as folders_router
from app.api.projects import router as projects_router
from app.api.search import router as search_router
from app.api.summary import router as summary_router

router = APIRouter(prefix="/api")

router.include_router(auth_router)
router.include_router(projects_router)
router.include_router(documents_router)
router.include_router(folders_router)
router.include_router(search_router)
router.include_router(chat_router)
router.include_router(summary_router)
router.include_router(admin_router)
