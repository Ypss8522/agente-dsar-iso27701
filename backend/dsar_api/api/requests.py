from flask import Blueprint, current_app, request

from ..errors import ok
from ..security import require_role
from ..services import request_service
from ..services.validators import clean_pagination

bp = Blueprint("requests", __name__)

ROLES = ("service", "dpo")


@bp.post("/requests")
@require_role(*ROLES)
def create_request():
    """Lo llama n8n al recibir el formulario. Responde con `ticket_id` para el frontend."""
    req = request_service.create_request(request.get_json(silent=True),
                                         submission_key=request.headers.get("Idempotency-Key"))
    return ok({"ticket_id": req.ticket_id, **req.to_dict()}, 201)


@bp.get("/requests")
@require_role(*ROLES)
def list_requests():
    """Alimenta el panel DPO (incluye `sla_days_remaining`)."""
    limit, offset = clean_pagination(
        request.args,
        default=current_app.config["DEFAULT_PAGE_SIZE"],
        maximum=current_app.config["MAX_PAGE_SIZE"],
    )
    total, rows = request_service.list_requests(
        status=request.args.get("status"),
        request_type=request.args.get("request_type"),
        overdue_only=request.args.get("overdue") == "true",
        limit=limit,
        offset=offset,
    )
    return ok([r.to_dict() for r in rows], total=total, limit=limit, offset=offset)


@bp.get("/requests/<ticket_id>")
@require_role(*ROLES)
def get_request(ticket_id):
    return ok(request_service.get_request(ticket_id).to_dict())


@bp.patch("/requests/<ticket_id>/status")
@require_role(*ROLES)
def update_status(ticket_id):
    req = request_service.update_status(ticket_id, request.get_json(silent=True))
    return ok(req.to_dict())
