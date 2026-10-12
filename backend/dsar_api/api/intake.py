"""Entrada pública: sólo registra solicitudes, nunca devuelve datos del titular."""
import json
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

from flask import Blueprint, current_app, g, request

from ..errors import ApiError, ForbiddenError, ok
from ..extensions import db
from ..models import Submission
from ..services.request_service import create_request, validated_payload, validate_submission_key

bp = Blueprint("intake", __name__)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Nunca reenviar la credencial del webhook a otra URL.


def forward_to_n8n(payload, key):
    url = current_app.config["N8N_WEBHOOK_URL"]
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ApiError("N8N_WEBHOOK_URL no es una URL HTTP válida.", code="n8n_config_error", status_code=503)
    headers = {"Content-Type": "application/json", "Idempotency-Key": key}
    token = current_app.config["N8N_WEBHOOK_TOKEN"]
    if not token:
        raise ApiError("Configura N8N_WEBHOOK_TOKEN para autenticar el webhook.", code="n8n_config_error", status_code=503)
    headers["X-Webhook-Token"] = token
    upstream = Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        # Servicios internos: no enviar tokens/datos a un proxy heredado del shell.
        with build_opener(ProxyHandler({}), NoRedirect()).open(upstream, timeout=current_app.config["N8N_TIMEOUT_SECONDS"]) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError("Respuesta demasiado grande")
            result = json.loads(raw)
    except HTTPError as exc:
        raise ApiError(f"El flujo n8n respondió HTTP {exc.code}. Revisa que esté publicado y sus credenciales.",
                       code="n8n_http_error", status_code=502) from exc
    except (socket.timeout, TimeoutError) as exc:
        raise ApiError("n8n tardó demasiado. Reintenta sin cambiar el formulario para conservar el mismo ticket.",
                       code="n8n_timeout", status_code=504) from exc
    except URLError as exc:
        code = "n8n_timeout" if isinstance(exc.reason, (socket.timeout, TimeoutError)) else "n8n_unreachable"
        raise ApiError("No se pudo conectar con n8n. Revisa el servicio, puerto y N8N_WEBHOOK_URL.",
                       code=code, status_code=504 if code == "n8n_timeout" else 503) from exc
    except OSError as exc:
        raise ApiError("La conexión con n8n se cerró. Revisa el servicio y reintenta sin cambiar los datos.",
                       code="n8n_unreachable", status_code=503) from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise ApiError("n8n no devolvió JSON válido.", code="n8n_invalid_response", status_code=502) from exc
    if (not isinstance(result, dict) or result.get("status") != "success"
            or not isinstance(result.get("ticket_id"), str)
            or not re.fullmatch(r"DSAR-[A-F0-9]{8}", result["ticket_id"])):
        raise ApiError("n8n no confirmó un ticket válido.", code="n8n_invalid_response", status_code=502)
    # Confirmar que el ticket efectivamente existe y pertenece a esta solicitud.
    if db.session.get(Submission, key) is None:
        raise ApiError("n8n respondió sin registrar la solicitud en Flask con su clave de reintento.",
                       code="n8n_invalid_response", status_code=502)
    req = create_request(payload, submission_key=key)
    if req.ticket_id != result["ticket_id"]:
        raise ApiError("El ticket de n8n no corresponde a la solicitud registrada.", code="n8n_invalid_response", status_code=502)
    return req


@bp.post("/intake")
def intake():
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") != request.host_url.rstrip("/") and origin not in current_app.config["CORS_ORIGINS"]:
        raise ForbiddenError("Abre el formulario desde el servidor Flask.", code="origin_not_allowed")
    payload = validated_payload(request.get_json())
    key = validate_submission_key(request.headers.get("Idempotency-Key"))
    if not key:
        from ..errors import ValidationError
        raise ValidationError("Idempotency-Key es obligatorio para registrar desde el portal.")
    if not current_app.config["AUDIT_HASH_KEY"]:
        raise ApiError("Prepara el backend con python scripts/setup.py.", code="backend_not_configured", status_code=503)
    g.actor = "portal"
    req = (forward_to_n8n(payload, key) if current_app.config["DSAR_INTAKE_MODE"] == "n8n" and db.session.get(Submission, key) is None
           else create_request(payload, submission_key=key))
    return ok({"ticket_id": req.ticket_id}, 201, ticket_id=req.ticket_id)
