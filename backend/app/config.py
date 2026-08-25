"""
Central configuration for the ATC Watch Beta backend.
All secrets are pulled from environment variables — nothing is hard-coded.
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---
    ENV: str = "development"
    SERVERLESS: bool = False
    CRON_SECRET: str = ""
    BACKEND_BASE_URL: str = "http://localhost:8000"
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    SECRET_KEY: str = "change-me-in-production"
    SESSION_COOKIE_NAME: str = "vatsim_atc_session"
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://vatsim:vatsim@localhost:5432/vatsim_atc_watch"

    # --- VATSIM Connect OAuth (https://auth.vatsim.net) ---
    VATSIM_CLIENT_ID: str = ""
    VATSIM_CLIENT_SECRET: str = ""
    VATSIM_OAUTH_AUTHORIZE_URL: str = "https://auth.vatsim.net/oauth/authorize"
    VATSIM_OAUTH_TOKEN_URL: str = "https://auth.vatsim.net/oauth/token"
    VATSIM_OAUTH_USERINFO_URL: str = "https://auth.vatsim.net/api/user"
    VATSIM_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/auth/callback"
    VATSIM_OAUTH_SCOPES: str = "full_name vatsim_details email"
    OAUTH_STATE_TTL_SECONDS: int = 600

    # --- VATSIM live data ---
    VATSIM_DATA_URL: str = "https://data.vatsim.net/v3/vatsim-data.json"
    VATSIM_STATUS_URL: str = "https://status.vatsim.net/status.json"
    VATSPY_DATA_URL: str = "https://raw.githubusercontent.com/vatsimnetwork/vatspy-data-project/master/VATSpy.dat"
    VATSPY_BOUNDARIES_URL: str = "https://raw.githubusercontent.com/vatsimnetwork/vatspy-data-project/master/Boundaries.geojson"
    VATSIM_POLL_INTERVAL_SECONDS: int = 15
    VATSIM_DATA_STALE_AFTER_SECONDS: int = 60

    # --- Web Push / VAPID ---
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIM_EMAIL: str = "mailto:admin@example.com"

    # --- Alert defaults (overridable per-user in Settings screen) ---
    DEFAULT_NOTIFY_MINUTES_BEFORE: int = 15
    DEFAULT_NOTIFY_NM_BEFORE: int = 100
    DEFAULT_TRAFFIC_RADIUS_NM: int = 150
    DEFAULT_ALTITUDE_FILTER_FT: int = 10000


@lru_cache
def get_settings() -> Settings:
    return Settings()
