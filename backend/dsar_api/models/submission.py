"""Idempotencia en tabla nueva: no modifica columnas de bases existentes."""
from ..extensions import db


class Submission(db.Model):
    __tablename__ = "request_submissions"
    key = db.Column(db.String(80), primary_key=True)
    fingerprint = db.Column(db.String(64), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey("dsar_requests.id"), nullable=False)
    request = db.relationship("DsarRequest")
