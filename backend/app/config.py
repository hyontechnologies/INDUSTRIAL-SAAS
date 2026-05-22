"""
Piccadily Industrial Historian — Application Configuration
Pydantic-settings based configuration with .env support.
"""

from typing import Dict, List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Industrial Operations Cloud"
    APP_VERSION: str = "4.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    TRUSTED_HOSTS: str = "*"  # comma-separated; "*" disables host check

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/historian"
    DB_POOL_MIN: int = 2
    DB_POOL_MAX: int = 8
    DB_WRITE_POOL_MAX: int = 10  # keep low on 4 GB RAM
    DB_POOL_MAX_INACTIVE: float = 300.0
    DB_COMMAND_TIMEOUT: float = 30.0
    DB_CONNECT_RETRIES: int = 10  # startup retry attempts
    DB_CONNECT_RETRY_DELAY: float = 3.0  # base delay (doubles each attempt)

    # ── Redis (Streams + Pub/Sub) ────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_STREAM_PREFIX: str = "historian:telemetry:"
    REDIS_STREAM_MAXLEN: int = 100000
    REDIS_CONSUMER_BATCH_SIZE: int = 2000
    REDIS_CONSUMER_WORKERS: int = 2
    REDIS_ALARM_WORKERS: int = 1
    REDIS_BLOCK_MS: int = 2000

    # ── Tailscale ────────────────────────────────────────────────────────────
    TAILSCALE_ENABLED: bool = False
    TAILSCALE_CLOUD_HOSTNAME: str = "historian-cloud"

    # ── Supabase Auth ────────────────────────────────────────────────────────
    SUPABASE_JWT_SECRET: str = "supabase_test_jwt_secret_placeholder_for_ci"
    SUPABASE_URL: str = "https://supabase-placeholder-project-url.supabase.co"
    JWT_ALGORITHM: str = "HS256"
    JWT_AUDIENCE: str = "authenticated"

    # ── Edge API Keys  (env-var fallback; DB api_keys table takes priority) ──
    # Format: "tenant_a:sha256hash,tenant_b:sha256hash"
    EDGE_API_KEYS: str = ""

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ── Telemetry ────────────────────────────────────────────────────────────
    TELEMETRY_BATCH_MAX: int = 500
    ALARM_COOLDOWN_SECONDS: int = 300  # 5 min: suppress duplicate alarms per tag
    ALARM_SWEEP_INTERVAL: int = 10  # background sweep every N seconds
    ALARM_CACHE_TTL: int = 60  # seconds to cache DB alarm thresholds
    STALE_TAG_MINUTES: int = 10  # tag not updated in N min → stale

    # ── Rate Limiting (in-memory, per tenant) ─────────────────────────────────
    RATE_LIMIT_POINTS_PER_MIN: int = 5000  # telemetry points per tenant per minute

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def trusted_hosts_list(self) -> List[str]:
        return [h.strip() for h in self.TRUSTED_HOSTS.split(",") if h.strip()]

    @property
    def edge_api_keys_map(self) -> Dict[str, str]:
        """Returns {sha256_hex: tenant_id} from env var (fallback)."""
        out: Dict[str, str] = {}
        for pair in self.EDGE_API_KEYS.split(","):
            pair = pair.strip()
            if ":" in pair:
                tid, khash = pair.split(":", 1)
                out[khash.strip()] = tid.strip()
        return out


settings = Settings()
