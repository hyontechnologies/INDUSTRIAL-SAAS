"""
Piccadily Industrial Historian — FastAPI Application Factory
Slim entry point: lifespan, middleware, router registration.
"""

import asyncio
import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from .alarms import alarm_sweep_loop
from .broadcaster import ws_manager
from .config import settings
from .database import close_pool, create_pool, get_pool
from .metrics import metrics

# ── Structured logging setup ────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger("historian.app")

# ── Router imports ──────────────────────────────────────────────────────────────
from .routers import admin, alarms, grafana, plants, tags, telemetry, websocket  # noqa: E402


# ── Lifespan ────────────────────────────────────────────────────────────────────
from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup.begin", app=settings.APP_NAME, version=settings.APP_VERSION, env=settings.ENVIRONMENT)

    await create_pool()
    log.info("startup.db_pool_ready", min=settings.DB_POOL_MIN, max=settings.DB_POOL_MAX)

    # Schema integrity check
    pool = get_pool()
    async with pool.acquire() as conn:
        ht_count = await conn.fetchval("SELECT count(*) FROM timescaledb_information.hypertables")
        if ht_count < 3:
            log.warning(
                "startup.schema_warning", msg="Expected ≥3 hypertables. Run init.sql if not done.", found=ht_count
            )
        else:
            log.info("startup.schema_ok", hypertables=ht_count)

    sweep_task = asyncio.create_task(alarm_sweep_loop())
    log.info("startup.alarm_sweep_started")

    yield  # ← application runs

    # Graceful drain
    sweep_task.cancel()
    try:
        await asyncio.wait_for(sweep_task, timeout=5.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass

    await close_pool()
    log.info("shutdown.complete")


# ── App factory ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ── Middleware stack (applied in reverse order) ─────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

if settings.ENVIRONMENT == "production" and settings.TRUSTED_HOSTS != "*":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts_list,
    )


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=rid, path=request.url.path)
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    log.info("http.request", method=request.method, status=response.status_code, ms=round(elapsed, 2))
    response.headers["X-Request-ID"] = rid
    return response


# ── Register routers ────────────────────────────────────────────────────────────
app.include_router(telemetry.router)
app.include_router(alarms.router)
app.include_router(tags.router)
app.include_router(plants.router)
app.include_router(admin.router)
app.include_router(websocket.router)
app.include_router(grafana.router)


# ── Health & Metrics (not in routers — these are ops-only) ──────────────────────
@app.get("/health", tags=["ops"], include_in_schema=False)
async def health():
    db_ok = False
    db_ms = None
    try:
        t0 = time.perf_counter()
        pool = get_pool()
        async with pool.acquire() as c:
            await c.fetchval("SELECT 1")
        db_ms = round((time.perf_counter() - t0) * 1000, 2)
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "db_latency_ms": db_ms,
        "ws_connections": ws_manager.connection_count,
        "points_ingested": metrics.points_total,
        "uptime_seconds": metrics.uptime_seconds,
        "version": settings.APP_VERSION,
    }


@app.get("/metrics", tags=["ops"], include_in_schema=False, response_class=PlainTextResponse)
async def prometheus_metrics():
    return metrics.prometheus_text()


@app.get("/ping", tags=["ops"], include_in_schema=False)
async def ping():
    from datetime import datetime, timezone

    return {"pong": True, "ts": datetime.now(timezone.utc).isoformat()}


# ── Global exception handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    metrics.errors_total += 1
    log.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Entry point ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=2,
        loop="uvloop",
        http="httptools",
        log_level="warning",
        access_log=False,
    )
