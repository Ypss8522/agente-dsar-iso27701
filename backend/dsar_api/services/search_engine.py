"""Adaptador entre la API autenticada y el motor FAISS del equipo."""
from ai_engine.search_engine import SearchUnavailable, buscar_pii_vectorial, validar_consulta

from ..errors import ApiError, ValidationError
from . import audit_service
from .validators import require_json
from .validators import clean_document_id


def search(payload):
    payload = require_json(payload)
    query, k = payload.get('query'), payload.get('k', 5)
    try:
        query = validar_consulta(query, k)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    user_id = clean_document_id(payload['user_id']) if 'user_id' in payload else None
    try:
        results = (buscar_pii_vectorial(query, k, user_id=user_id) if user_id is not None
                   else buscar_pii_vectorial(query, k))
    except SearchUnavailable as exc:
        raise ApiError(str(exc), code='vector_search_unavailable', status_code=503) from exc
    except Exception as exc:
        # Evitar que un traceback del encoder exponga la consulta o documentos.
        raise ApiError('No se pudo completar la búsqueda vectorial.',
                       code='vector_search_failed', status_code=500) from exc
    audit_service.record('VECTOR_SEARCH', entity_type='document',
                         detail={'k': k, 'count': len(results)})
    return {'results': results, 'count': len(results), 'metric': 'cosine_similarity'}
