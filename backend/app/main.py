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

from .alarms import evict_threshold_cache
from .broadcaster import ws_manager
from .config import settings
from .database import close_pools, create_pools, get_read_pool
from .metrics import metrics
from .stream_writer import init_redis_pool, close_redis_pool, redis_client
from .stream_consumer import stream_consumer_worker
from .alarm_consumer import alarm_consumer_worker

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

    await create_pools()
    await init_redis_pool()
    log.info("startup.db_pool_ready", min=settings.DB_POOL_MIN, max=settings.DB_POOL_MAX)

    # Schema integrity check
    pool = get_read_pool()
    async with pool.acquire() as conn:
        ht_count = await conn.fetchval("SELECT count(*) FROM timescaledb_information.hypertables")
        if ht_count < 3:
            log.warning(
                "startup.schema_warning", msg="Expected ≥3 hypertables. Run init.sql if not done.", found=ht_count
            )
        else:
            log.info("startup.schema_ok", hypertables=ht_count)

    # Start Redis consumer workers
    writer_tasks = [asyncio.create_task(stream_consumer_worker(i)) for i in range(settings.REDIS_CONSUMER_WORKERS)]
    alarm_tasks = [asyncio.create_task(alarm_consumer_worker(i)) for i in range(settings.REDIS_ALARM_WORKERS)]
    log.info("startup.workers_started", writers=len(writer_tasks), alarms=len(alarm_tasks))

    await ws_manager.start_pubsub()

    yield  # ← application runs

    # Graceful drain
    log.info("shutdown.draining_workers")
    for task in writer_tasks + alarm_tasks:
        task.cancel()

    try:
        await asyncio.gather(*writer_tasks, *alarm_tasks, return_exceptions=True)
    except Exception:
        pass

    await ws_manager.stop_pubsub()
    await close_redis_pool()
    await close_pools()
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
    redis_ok = False
    db_ms = None
    try:
        t0 = time.perf_counter()
        pool = get_read_pool()
        async with pool.acquire() as c:
            await c.fetchval("SELECT 1")
        db_ms = round((time.perf_counter() - t0) * 1000, 2)
        db_ok = True
    except Exception:
        pass

    try:
        if redis_client:
            await redis_client.ping()
            redis_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "db": db_ok,
        "redis": redis_ok,
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


# ── Serve Frontend SPA ────────────────────────────────────────────────────────
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))

if os.path.exists(static_dir):
    log.info("startup.frontend_static_serving", path=static_dir)
    # Mount `/assets` first if it exists, to leverage FastAPI's highly optimized static files engine for large bundles
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # SPA wildcard catch-all route to serve the built frontend
    @app.get("/{catchall:path}", include_in_schema=False)
    async def serve_spa(catchall: str):
        # Exclude backend namespaces explicitly to prevent circular loops
        if catchall.startswith("api/") or catchall.startswith("ws/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        file_path = os.path.join(static_dir, catchall)
        if catchall and os.path.isfile(file_path):
            return FileResponse(file_path)

        # Serve index.html for client-side SPA routing fallbacks
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)

        return PlainTextResponse("Not Found", status_code=404)
else:
    log.warning(
        "startup.frontend_static_not_found",
        path=static_dir,
        msg="Frontend static files folder not found. Running API-only mode.",
    )


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
