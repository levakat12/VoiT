from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers.jobs import router as jobs_router
from app.routers.settings import router as settings_router

settings = get_settings()

app = FastAPI(title="VoiT API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(jobs_router, prefix="/api", tags=["transcripts"])
app.include_router(settings_router, prefix="/api", tags=["settings"])
