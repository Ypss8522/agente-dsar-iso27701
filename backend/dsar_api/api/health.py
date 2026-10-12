from flask import Blueprint
from sqlalchemy import text, inspect

from ..errors import ok, ApiError
from ..extensions import db

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    db.session.execute(text("SELECT 1"))
    tables = set(inspect(db.engine).get_table_names())
    if not {"data_subjects", "dsar_requests", "audit_logs", "request_submissions"} <= tables:
        raise ApiError("Inicializa las tablas con python scripts/setup.py o flask --app app init-db.",
                       code="database_not_initialized", status_code=503)
    return ok({"service": "dsar-backend", "database": "up"})
