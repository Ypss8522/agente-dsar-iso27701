"""Application factory del backend DSAR (ISO/IEC 27701)."""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request

from .errors import register_error_handlers
from .extensions import cors, db


def create_app(config_name: str | None = None) -> Flask:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    # La configuración lee el entorno al importar: cargar .env antes.
    from .config import ProductionConfig, get_config, environment_overrides

    # Directorio real: funciona también en Windows y en ZIP sin symlinks.
    static_dir = Path(__file__).resolve().parents[2] / 'frontend'
    app = Flask(__name__, instance_relative_config=False,
                static_folder=str(static_dir), static_url_path='/static')
    config = get_config(config_name)
    if config is ProductionConfig:
        ProductionConfig.validate()
    app.config.from_object(config)
    if not app.config.get("TESTING"):
        app.config.update(environment_overrides())
    if app.config["DSAR_INTAKE_MODE"] not in ("direct", "n8n"):
        raise RuntimeError("DSAR_INTAKE_MODE debe ser direct o n8n.")
    if not 1 <= app.config["N8N_TIMEOUT_SECONDS"] <= 30:
        raise RuntimeError("N8N_TIMEOUT_SECONDS debe estar entre 1 y 30.")

    # Carpeta para la BD SQLite local (ignorada por git).
    (Path(__file__).resolve().parent.parent / "instance").mkdir(exist_ok=True)

    db.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        allow_headers=["Content-Type", "X-API-Key", "Idempotency-Key"],
    )

    from . import models  # noqa: F401  (registra tablas en el metadata)
    from .api import register_blueprints
    from .cli import register_cli

    register_blueprints(app)
    register_error_handlers(app)
    register_cli(app)

    @app.after_request
    def private_responses(response):
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.get('/')
    def portal():
        return app.send_static_file('index.html')

    @app.get('/dpo')
    def dpo_panel():
        return app.send_static_file('dpo.html')

    if app.config.get("TESTING"):
        with app.app_context():
            db.create_all()

    return app
