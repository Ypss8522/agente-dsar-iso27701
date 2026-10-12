"""Lógica de negocio sobre titulares: consulta, rectificación y supresión."""
from __future__ import annotations

from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db
from ..models import DataSubject, DsarRequest
from ..models.data_subject import utcnow
from . import audit_service
from .validators import clean_document_id, clean_email, clean_text, require_json


def get_subject(document_id: str) -> DataSubject:
    subject = DataSubject.query.filter_by(document_id=document_id).first()
    if subject is None:
        audit_service.record(
            "SUBJECT_LOOKUP", entity_type="data_subject", document_id=document_id,
            outcome="denied", detail={"reason": "not_found"},
        )
        raise NotFoundError("No existe un titular con ese identificador.")
    return subject


def create_subject(payload) -> DataSubject:
    payload = require_json(payload)
    document_id = clean_document_id(payload.get("user_id"))
    if DataSubject.query.filter_by(document_id=document_id).first():
        raise ConflictError("Ya existe un titular con ese identificador.")
    subject = DataSubject(
        document_id=document_id,
        full_name=clean_text(payload.get("nombre"), field="nombre", max_len=200),
        email=clean_email(payload["email"]) if payload.get("email") else None,
    )
    db.session.add(subject)
    db.session.flush()
    # Vincular solicitudes recibidas antes de dar de alta al titular.
    DsarRequest.query.filter_by(document_id=document_id, subject_id=None).update({"subject_id": subject.id})
    audit_service.record(
        "SUBJECT_CREATED", entity_type="data_subject", entity_id=str(subject.id),
        document_id=document_id, commit=False,
    )
    db.session.commit()
    return subject


def access_data(document_id: str, *, portable: bool = False, ticket_id: str | None = None) -> dict:
    """Derechos de Acceso / Portabilidad: devuelve los datos del titular y sus solicitudes."""
    document_id = clean_document_id(document_id)
    subject = get_subject(document_id)
    data = subject.to_dict()
    data["solicitudes"] = [r.to_dict() for r in subject.requests.order_by(None).all()]
    audit_service.record(
        "USER_DATA_PORTABILITY" if portable else "USER_DATA_ACCESS",
        entity_type="data_subject", entity_id=str(subject.id),
        document_id=document_id, ticket_id=ticket_id,
    )
    if portable:
        return {"format": "portable-json", "version": 1, "subject": data}
    return data


_RECTIFIABLE = ("nombre", "email")


def rectify(payload) -> DataSubject:
    """Derecho de Rectificación: sólo campos permitidos."""
    payload = require_json(payload)
    document_id = clean_document_id(payload.get("user_id"))
    changes = payload.get("changes")
    if not isinstance(changes, dict) or not changes:
        raise ValidationError("changes debe ser un objeto con al menos un campo.")
    unknown = set(changes) - set(_RECTIFIABLE)
    if unknown:
        raise ValidationError("Campos no rectificables: " + ", ".join(sorted(unknown)))

    subject = get_subject(document_id)
    if subject.is_anonymized:
        raise ConflictError("El titular ya fue anonimizado.", code="already_anonymized")

    changed = []
    if "nombre" in changes:
        subject.full_name = clean_text(changes["nombre"], field="nombre", max_len=200, required=True)
        changed.append("nombre")
    if "email" in changes:
        subject.email = clean_email(changes["email"])
        changed.append("email")

    audit_service.record(
        "USER_RECTIFIED", entity_type="data_subject", entity_id=str(subject.id),
        document_id=document_id, ticket_id=payload.get("ticket_id"),
        detail={"fields": changed}, commit=False,  # se registran campos, no valores
    )
    db.session.commit()
    return subject


def erase(payload) -> dict:
    """Derecho de Supresión: anonimiza al titular salvo que aplique retención legal."""
    payload = require_json(payload)
    document_id = clean_document_id(payload.get("user_id"))
    ticket_id = payload.get("ticket_id")
    subject = get_subject(document_id)

    reason = subject.retention_block_reason()
    if reason:
        audit_service.record(
            "USER_ERASURE", entity_type="data_subject", entity_id=str(subject.id),
            document_id=document_id, ticket_id=ticket_id, outcome="denied",
            detail={"reason": reason},
        )
        raise ConflictError(reason, code="retention_blocked")

    placeholder = f"ANON-{subject.id}"
    subject.full_name = None
    subject.email = None
    subject.document_id = placeholder
    subject.active = False
    subject.anonymized_at = utcnow()
    # Los PII duplicados en las solicitudes también se anonimizan; el ticket,
    # tipo y estado se conservan como evidencia de cumplimiento.
    for req in DsarRequest.query.filter_by(document_id=document_id).all():
        req.document_id = placeholder
        req.email = "anonimizado@invalid"
        req.details = None
        req.resolution_note = None

    audit_service.record(
        "USER_ERASURE", entity_type="data_subject", entity_id=str(subject.id),
        document_id=document_id, ticket_id=ticket_id, detail={"method": "anonymization"},
        commit=False,
    )
    db.session.commit()
    return {"anonymized": True, "subject_id": subject.id}
