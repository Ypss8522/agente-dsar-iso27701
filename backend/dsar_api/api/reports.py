from flask import Blueprint, request, send_file

from ..errors import ok
from ..security import require_role
from ..services.report_service import request_pdf
from ..services.redaction_service import redact
from ..services import audit_service

bp = Blueprint("reports", __name__)


@bp.get("/requests/<ticket_id>/report.pdf")
@require_role("dpo")
def report(ticket_id):
    return send_file(request_pdf(ticket_id), mimetype="application/pdf", as_attachment=True,
                     download_name=f"{ticket_id}.pdf")


@bp.post("/redact")
@require_role("service", "dpo")
def redact_text():
    result = redact(request.get_json())
    audit_service.record("TEXT_REDACTED", detail={"review_required": True})
    return ok(result)
