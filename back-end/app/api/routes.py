from fastapi import APIRouter, Request
from scalar_fastapi import get_scalar_api_reference

from app.auth.routes import router as auth_router
from app.users.routes import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)

@router.get("/docs", include_in_schema=False)
async def scalar_html(request: Request):
    return get_scalar_api_reference(openapi_url=request.app.openapi_url)


@router.get("/ping")
def ping():
    return {"message": "Pong!"}
