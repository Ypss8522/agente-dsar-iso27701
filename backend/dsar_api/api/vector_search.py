from flask import Blueprint, request

from ..errors import ok
from ..security import require_role
from ..services import search_engine
from ai_engine.search_engine import estado_ia

bp = Blueprint('vector_search', __name__)


@bp.get('/ai/status')
@require_role('dpo')
def ai_status():
    return ok(estado_ia())


@bp.post('/vector-search')
@require_role('service', 'dpo')
def vector_search():
    return ok(search_engine.search(request.get_json()))
