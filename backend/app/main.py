import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app import models
from app.database import Base, engine
from app.routes import (
    auth,
    cases,
    dashboard,
    documents,
    history,
    tasks,
    users,
)
from app.routes.timeline import router as timeline_router
from app.seed import create_users

load_dotenv()

Base.metadata.create_all(bind=engine)
create_users()

session_secret = os.getenv("SESSION_SECRET_KEY")

if not session_secret:
    raise RuntimeError(
        "SESSION_SECRET_KEY is missing from backend/.env"
    )

app = FastAPI(
    title="Case Flow API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="caseflow_session",
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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


@app.get("/")
def root():
    return {
        "message": "Case Flow API is running",
    }