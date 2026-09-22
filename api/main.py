# api/main.py
"""FastAPI application factory, lifespan management, and router mounting."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth_routes import router as auth_router, login as handle_login
from api.dependencies import get_store
from api.student_routes import router as student_router
from api.teacher_routes import router as teacher_router
from slice.store import Store
from synapse.api_contracts import AuthResponse, LoginRequest
from synapse.runtime.flow import sweep_expired
from web.expert import router as expert_router
from web.student import router as web_student_router
from web.teacher import router as web_teacher_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background sweep task for teacher confirmation deadlines
    store = get_store()
    # Initial sweep at startup
    try:
        sweep_expired(store)
    except Exception:
        pass

    stop_event = asyncio.Event()

    async def _periodic_sweep():
        while not stop_event.is_set():
            try:
                await asyncio.sleep(30)
                sweep_expired(store)
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    task = asyncio.create_task(_periodic_sweep())
    yield
    stop_event.set()
    task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Synapse Cycle API",
        version="2.0",
        description="Persistent AI Agent Runtime for Educational Diagnostics and Tailored Concept Notes",
        lifespan=lifespan,
    )

    # CORS configuration for modern React / Vite SPA frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routers
    app.include_router(auth_router)
    app.include_router(teacher_router)
    app.include_router(student_router)

    # Server-rendered web callback routers
    app.include_router(web_teacher_router)
    app.include_router(web_student_router)
    app.include_router(expert_router)

    # Auth route aliases for /login and /api/login guaranteeing 401 on invalid credentials (never 404)
    @app.post("/login", response_model=AuthResponse, tags=["auth"])
    @app.post("/api/login", response_model=AuthResponse, tags=["auth"])
    @app.post("/api/auth/login", response_model=AuthResponse, tags=["auth"])
    async def login_alias(
        req: LoginRequest,
        store: Store = Depends(get_store),
    ) -> AuthResponse:
        """Alias for /auth/login ensuring any direct /login call reaches the auth handler."""
        return await handle_login(req, store)

    @app.get("/login")
    async def login_page_redirect():
        """Redirect GET /login to the SPA login view instead of returning 404."""
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/app/#login")

    from pathlib import Path
    from fastapi.staticfiles import StaticFiles

    dist_path = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if dist_path.exists():
        app.mount("/app", StaticFiles(directory=str(dist_path), html=True), name="frontend")

    @app.get("/")
    async def root():
        if dist_path.exists():
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/app/")
        return {"status": "ok", "app": "Synapse Cycle", "docs": "/docs"}

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "app": "Synapse Cycle"}

    return app


app = create_app()
