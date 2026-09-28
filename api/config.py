"""
NetGuard AI — API configuration (api/config.py)
"""

import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings:
    model_dir: str = os.getenv("MODEL_DIR", str(REPO_ROOT / "ml" / "artifacts"))
    default_alert_threshold: float = float(os.getenv("ALERT_THRESHOLD", "0.85"))
    alert_dedup_seconds: int = int(os.getenv("ALERT_DEDUP_SECONDS", "30"))
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{REPO_ROOT / 'netguard.db'}")
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
    sensor_api_key: str = os.getenv("SENSOR_API_KEY", "dev-sensor-key-change-me")
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
        if o.strip()
    ]
    top_features_count: int = int(os.getenv("TOP_FEATURES_COUNT", "3"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()