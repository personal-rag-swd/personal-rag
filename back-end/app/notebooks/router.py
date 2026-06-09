from fastapi import APIRouter

from app.notebooks.routes.chat import router as chat_router
from app.notebooks.routes.crud import router as crud_router
from app.notebooks.routes.documents import router as documents_router
from app.notebooks.routes.events import router as events_router
from app.notebooks.routes.reports import router as reports_router

router = APIRouter(prefix="/notebooks", tags=["Notebooks"])
router.include_router(events_router)
router.include_router(crud_router)
router.include_router(documents_router)
router.include_router(chat_router)
router.include_router(reports_router)
