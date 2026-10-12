"""Ocultación asistida para revisión; no equivale a anonimización irreversible."""
import re

from ..errors import ValidationError
from .validators import clean_text, require_json


def redact(payload):
    payload = require_json(payload)
    text = clean_text(payload.get("text"), field="text", max_len=20000, required=True)
    values = payload.get("values", [])
    if not isinstance(values, list) or len(values) > 100 or any(
            not isinstance(v, str) or not 2 <= len(v.strip()) <= 200 for v in values):
        raise ValidationError("values debe ser una lista de hasta 100 textos de 2-200 caracteres.")
    patterns = [r"(?<![\w@])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?!\w)",
                r"(?<!\w)(?:\+51[ -]?)?\d{9}(?!\w)", r"(?<!\w)\d{8}(?!\w)"]
    for value in sorted(values, key=len, reverse=True):
        text = re.sub(r"(?<!\w)" + re.escape(value.strip()) + r"(?!\w)", "[DATO OCULTO]", text, flags=re.I)
    for pattern in patterns:
        text = re.sub(pattern, "[DATO OCULTO]", text)
    return {"text": text, "review_required": True,
            "notice": "Revisa nombres, direcciones y datos de terceros antes de entregar. Las reglas no detectan toda la PII."}
