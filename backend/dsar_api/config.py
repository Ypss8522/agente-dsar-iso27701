"""Configuración por entorno. Todo valor sensible viene de variables de entorno."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class BaseConfig:
    ENV_NAME = "base"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'instance' / 'dsar.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SERVICE_API_KEY = ""
    DPO_API_KEY = ""
    AUDIT_HASH_KEY = ""
    CORS_ORIGINS = ["http://localhost:5000", "http://127.0.0.1:5000"]
    # Plazo interno configurable; no implica un plazo legal universal.
    DSAR_SLA_DAYS = 30
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 200
    MAX_CONTENT_LENGTH = 64 * 1024
    DSAR_INTAKE_MODE = "direct"
    N8N_WEBHOOK_URL = "http://127.0.0.1:5678/webhook/dsar-request"
    N8N_TIMEOUT_SECONDS = 10
    N8N_WEBHOOK_TOKEN = ""


class DevelopmentConfig(BaseConfig):
    ENV_NAME = "development"
    DEBUG = True


class TestingConfig(BaseConfig):
    ENV_NAME = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SERVICE_API_KEY = "test-service-key"
    DPO_API_KEY = "test-dpo-key"
    AUDIT_HASH_KEY = "test-audit-key"


class ProductionConfig(BaseConfig):
    ENV_NAME = "production"
    DEBUG = False

    @classmethod
    def validate(cls) -> None:
        missing = [
            name
            for name in ("SERVICE_API_KEY", "DPO_API_KEY", "AUDIT_HASH_KEY", "DATABASE_URL")
            if not os.getenv(name)
        ]
        if missing:
            raise RuntimeError(
                "Faltan variables de entorno obligatorias en producción: " + ", ".join(missing)
            )


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None):
    name = name or os.getenv("APP_ENV", "development")
    try:
        return CONFIGS[name]
    except KeyError:
        raise RuntimeError(f"APP_ENV desconocido: {name!r}. Usa: {', '.join(CONFIGS)}")


def environment_overrides():
    """Leer por factory: evita usar claves antiguas después de cargar otro .env."""
    values = {name: os.environ[name] for name in (
        "DATABASE_URL", "SERVICE_API_KEY", "DPO_API_KEY", "AUDIT_HASH_KEY",
        "DSAR_INTAKE_MODE", "N8N_WEBHOOK_URL", "N8N_WEBHOOK_TOKEN",
    ) if name in os.environ}
    if "DATABASE_URL" in values:
        values["SQLALCHEMY_DATABASE_URI"] = values.pop("DATABASE_URL")
    if "CORS_ORIGINS" in os.environ:
        values["CORS_ORIGINS"] = _csv(os.environ["CORS_ORIGINS"])
    for name in ("DSAR_SLA_DAYS", "N8N_TIMEOUT_SECONDS"):
        if name in os.environ:
            values[name] = int(os.environ[name])
    return values
