from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference

from app.auth.router import router as auth_router
from app.users.router import router as users_router

app = FastAPI(title="Personal RAG", docs_url=None, redoc_url=None)


@app.get("/docs", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )


@app.get("/ping")
async def ping():
    return {"ping": "pong"}


app.include_router(auth_router)
app.include_router(users_router)

