from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.database import engine
from app.models import ApiKey, Observation, Station, UserAnnotation  # noqa: F401 — imported so Alembic can detect models

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing to do — Alembic manages schema
    yield
    # Shutdown: dispose engine
    await engine.dispose()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    contact={"name": "COMP3011 Project", "email": "sc23maa@leeds.ac.uk"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "stations", "description": "Weather station CRUD operations"},
        {"name": "observations", "description": "Daily climate observation CRUD"},
        {"name": "annotations", "description": "User-submitted notes and corrections"},
        {"name": "analytics", "description": "Statistical analysis and trend endpoints"},
        {"name": "health", "description": "API health check"},
    ],
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — open for academic demo purposes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global 404 handler with consistent error envelope
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "NotFound", "detail": str(exc.detail), "status_code": 404},
    )


@app.exception_handler(422)
async def validation_handler(request: Request, exc):
    detail = exc.errors() if hasattr(exc, "errors") else str(exc.detail)
    return JSONResponse(
        status_code=422,
        content={"error": "ValidationError", "detail": detail, "status_code": 422},
    )


# Register routers (imported here to avoid circular imports)
from app.routers import analytics, annotations, observations, stations  # noqa: E402

app.include_router(stations.router, prefix="/stations", tags=["stations"])
app.include_router(observations.router, prefix="/observations", tags=["observations"])
app.include_router(annotations.router, prefix="/annotations", tags=["annotations"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])


@app.get("/health", tags=["health"], summary="Health check")
async def health_check():
    """Returns API status. Used by deployment platforms to verify the service is alive."""
    return {"status": "ok", "version": settings.api_version}


@app.get("/", tags=["health"], include_in_schema=False)
async def root():
    return {
        "message": "UK Climate Insights API",
        "docs": "/docs",
        "redoc": "/redoc",
        "dashboard": "/ui",
        "version": settings.api_version,
    }


# ── Frontend dashboard (static files) ────────────────────────────────────────
_STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/ui", include_in_schema=False)
async def dashboard_home():
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/ui/{page}", include_in_schema=False)
async def dashboard_page(page: str):
    html_file = _STATIC_DIR / f"{page}.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return FileResponse(str(_STATIC_DIR / "index.html"))
