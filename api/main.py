"""
FastAPI application entry point for Synapse.
Authoritative contract: Contracts.md Sections C.4, D.2, D.5, D.6, F.3.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.runs import router as runs_router
from api.student import router as student_router
from api.teacher import router as teacher_router
from synapse.runtime.service import sweep_expired
from web.student import router as web_student_router
from web.teacher import router as web_teacher_router


async def _background_sweep_loop():
    """Run callback.sweep periodically to expire stale human-in-the-loop questions."""
    while True:
        try:
            sweep_expired()
        except Exception:
            pass
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: sweep once immediately and start 30s background ticker
    try:
        sweep_expired()
    except Exception:
        pass
    sweep_task = asyncio.create_task(_background_sweep_loop())
    yield
    # Shutdown: cancel background task
    sweep_task.cancel()
    try:
        await sweep_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Synapse API",
    description="Adaptive learning system with human-in-the-loop teacher confirmation and verifiable audit trails.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API and Web routers
app.include_router(teacher_router)
app.include_router(student_router)
app.include_router(runs_router)
app.include_router(web_teacher_router)
app.include_router(web_student_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "synapse"}
