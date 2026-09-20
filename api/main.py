"""Main FastAPI Application Entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.models import HealthResponse
from api.routes import auth, questions, runs

app = FastAPI(
    title="Synapse Cycle API",
    description="Person 5 API foundation for Guardian Agents",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(runs.router)
app.include_router(questions.router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Basic health check endpoint."""
    return HealthResponse(status="ok")
