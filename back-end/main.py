from fastapi import FastAPI

from app.api.routes import router


app = FastAPI(title="Personal RAG", docs_url=None, redoc_url=None)
app.include_router(router)
