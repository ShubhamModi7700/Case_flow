import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app import models 
from app.routes import ai, assistant, auth, cases, dashboard, documents, history, tasks, users
from app.routes.timeline import router as timeline_router

load_dotenv()


def _allowed_origins() -> list[str]:
    configured = os.getenv("FRONTEND_URLS") or os.getenv("FRONTEND_URL", "")

    origins = {
        value.strip().rstrip("/")
        for value in configured.split(",")
        if value.strip()
    }

    origins.update(
        {
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        }
    )

    return sorted(origins)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


session_secret = os.getenv("SESSION_SECRET_KEY", "").strip()

if not session_secret:
    raise RuntimeError("SESSION_SECRET_KEY is missing")

is_production = (
    os.getenv("ENVIRONMENT", "development").strip().lower()
    == "production"
)

app = FastAPI(
    title="Case Flow API",
    version="1.1.1",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="caseflow_session",
    max_age=60 * 60 * 8,
    same_site="none" if is_production else "lax",
    https_only=is_production,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(tasks.router)
app.include_router(dashboard.router)
app.include_router(history.router)
app.include_router(timeline_router)
app.include_router(documents.router)
app.include_router(users.router)
app.include_router(ai.router)
app.include_router(assistant.router)


@app.get("/")
def root():
    return {
        "message": "Case-Flow API ist aktiv",
        "version": "1.1.1",
    }


@app.get("/health")
def health():
    return {"status": "ok"}