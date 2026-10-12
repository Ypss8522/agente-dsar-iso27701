# ai_engine/search_engine.py
import os
import re
import json
import hashlib
from functools import lru_cache
from pathlib import Path
from threading import RLock

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, 'documentos')
DATA_DIR = os.path.join(BASE_DIR, 'data')
INDEX_PATH = os.path.join(DATA_DIR, 'faiss.index')
META_PATH = os.path.join(DATA_DIR, 'chunks.json')
MODEL_NAME = os.getenv('EMBEDDING_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')

_model = None
_index = None
_chunks = []
_lock = RLock()


class SearchUnavailable(RuntimeError):
    """Dependencias, modelo o índice local no disponibles."""


@lru_cache(maxsize=4)
def _model_identity(model_name):
    """Identidad por contenido: el mismo modelo puede copiarse a otro host/Docker."""
    root = Path(model_name)
    if not root.is_dir():
        return 'name:' + model_name
    digest = hashlib.sha256()
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix in ('.json', '.safetensors', '.bin', '.txt', '.model'))
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b'\x00')
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
    return 'sha256:' + digest.hexdigest()


def _dimension():
    model = _get_model()
    method = getattr(model, 'get_embedding_dimension', None) or model.get_sentence_embedding_dimension
    return method()


def validar_consulta(query_text, k=5):
    if not isinstance(query_text, str) or not query_text.strip():
        raise ValueError('query debe ser texto no vacío.')
    if len(query_text) > 4000:
        raise ValueError('query admite hasta 4000 caracteres.')
    if type(k) is not int or not 1 <= k <= 50:
        raise ValueError('k debe ser un entero entre 1 y 50.')
    return query_text.strip()


def _dependencias():
    # El backend estructurado puede arrancar sin instalar el motor de IA.
    global np, faiss
    try:
        import numpy as np
        import faiss
    except ImportError as exc:
        raise SearchUnavailable('Instala ai_engine/requirements.txt para usar FAISS.') from exc


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Preparar el modelo antes de arrancar: las consultas nunca lo descargan.
            _model = SentenceTransformer(MODEL_NAME, device='cpu', local_files_only=True)
        except Exception as exc:
            raise SearchUnavailable('El modelo local no está disponible. Prepara EMBEDDING_MODEL.') from exc
    return _model


def _leer_archivo(ruta):
    if ruta.endswith('.pdf'):
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(ruta).pages)
    with open(ruta, encoding='utf-8') as f:
        return f.read()


def _dividir(texto, tam=500, solape=50):
    trozos = (texto[i:i + tam] for i in range(0, len(texto), tam - solape))
    return [t for t in trozos if t.strip()]


def _texto_para_vector(chunk):
    """Agrega el nombre del documento al texto para que cada trozo 'sepa' de quién es."""
    nombre = chunk['fuente'].replace('_', ' ').replace('.txt', '').replace('.pdf', '')
    return nombre + ': ' + chunk['texto']


def construir_indice():
    """Lee ai_engine/documentos, genera vectores y guarda el índice."""
    with _lock:
        return _construir_indice()


def _construir_indice():
    global _index, _chunks
    _dependencias()
    chunks = []
    for nombre in sorted(os.listdir(DOCS_DIR)):
        if nombre.endswith(('.pdf', '.txt')):
            for c in _dividir(_leer_archivo(os.path.join(DOCS_DIR, nombre))):
                chunks.append({'texto': c, 'fuente': nombre})
    if not chunks:
        raise ValueError('No hay documentos .txt/.pdf en ' + DOCS_DIR)

    vectores = _get_model().encode(
        [_texto_para_vector(c) for c in chunks],
        normalize_embeddings=True)
    vectores = np.ascontiguousarray(vectores, dtype='float32')
    if vectores.shape != (len(chunks), _dimension()) or not np.isfinite(vectores).all():
        raise SearchUnavailable('El modelo produjo embeddings inválidos.')
    index = faiss.IndexFlatIP(vectores.shape[1])  # similitud coseno
    index.add(vectores)

    os.makedirs(DATA_DIR, exist_ok=True)
    faiss.write_index(index, INDEX_PATH)
    with open(META_PATH, 'w', encoding='utf-8') as f:
        json.dump({'model': MODEL_NAME, 'model_id': _model_identity(MODEL_NAME), 'chunks': chunks}, f, ensure_ascii=False)
    _index, _chunks = index, chunks
    return len(chunks)


def _asegurar_indice():
    global _index, _chunks
    if _index is None:
        _dependencias()
        if not os.path.exists(INDEX_PATH) or not os.path.exists(META_PATH):
            raise SearchUnavailable('No hay índice local. Ejecuta python -m ai_engine.search_engine.')
        try:
            index = faiss.read_index(INDEX_PATH)
            with open(META_PATH, encoding='utf-8') as f:
                metadata = json.load(f)
            # Los índices anteriores no registraban el modelo; reconstruirlos.
            if not isinstance(metadata, dict) or metadata.get('model_id') != _model_identity(MODEL_NAME):
                raise ValueError('El índice no corresponde al modelo configurado.')
            chunks = metadata['chunks']
            if not isinstance(chunks, list) or not chunks or index.ntotal != len(chunks):
                raise ValueError('Índice y metadatos incompatibles.')
            if any(not isinstance(c, dict) or not isinstance(c.get('texto'), str)
                   or not isinstance(c.get('fuente'), str) for c in chunks):
                raise ValueError('Metadatos inválidos.')
            if index.d != _dimension() or index.metric_type != faiss.METRIC_INNER_PRODUCT:
                raise ValueError('Dimensión o métrica incompatible.')
        except SearchUnavailable:
            raise
        except Exception as exc:
            raise SearchUnavailable('Índice inválido: reconstruye el índice local.') from exc
        _index, _chunks = index, chunks


def estado_ia():
    """Comprueba modelo e índice reales, sin descargas ni rutas en la respuesta."""
    try:
        with _lock:
            _asegurar_indice()
            return {'ready': True, 'chunks': len(_chunks),
                    'documents': len({c['fuente'] for c in _chunks}),
                    'message': 'IA local lista para buscar documentos.'}
    except SearchUnavailable:
        return {'ready': False, 'chunks': 0, 'documents': 0,
                'message': 'La IA necesita preparación. Inicia el proyecto con iniciar.py.'}
    except Exception:
        return {'ready': False, 'chunks': 0, 'documents': 0,
                'message': 'No se pudo comprobar la IA. Vuelve a preparar el modelo y el índice.'}


def buscar_pii_vectorial(query_text, k=5, *, user_id=None):
    """Búsqueda por significado. Devuelve lista de {texto, fuente, score}."""
    query_text = validar_consulta(query_text, k)
    with _lock:
        _asegurar_indice()
        # Seleccionar documentos por una referencia literal, antes de ordenarlos
        # por significado. La similitud por sí sola no identifica al titular.
        sources = None
        if user_id is not None:
            user_id = validar_consulta(user_id)
            pattern = re.compile(r'(?<!\w)' + re.escape(user_id) + r'(?!\w)', re.IGNORECASE)
            sources = {c['fuente'] for c in _chunks if pattern.search(c['texto'])}
            if not sources:
                return []
        vector = _get_model().encode([query_text], normalize_embeddings=True)
        vector = np.ascontiguousarray(vector, dtype='float32')
        if vector.shape != (1, _index.d) or not np.isfinite(vector).all():
            raise SearchUnavailable('Embedding local inválido.')
        scores, ids = _index.search(vector, _index.ntotal if sources is not None else min(k, _index.ntotal))
        return [
            {'texto': _chunks[i]['texto'], 'fuente': _chunks[i]['fuente'],
             'score': float(s)}
            for s, i in zip(scores[0], ids[0]) if 0 <= i < len(_chunks) and np.isfinite(s)
            and (sources is None or _chunks[i]['fuente'] in sources)
        ][:k]


def buscar_exacta(termino):
    """Búsqueda literal (DNI, correo, nombre), solo coincidencias completas."""
    termino = validar_consulta(termino)
    with _lock:
        _asegurar_indice()
        patron = re.compile(r'(?<!\w)' + re.escape(termino) + r'(?!\w)', re.IGNORECASE)
        return [
            {'texto': c['texto'], 'fuente': c['fuente'], 'score': 1.0}
            for c in _chunks if patron.search(c['texto'])
        ]


def _mostrar(resultados):
    for r in resultados:
        texto = r['texto'].replace('\n', ' ')[:90]
        print(f"  {r['score']:.3f} | {r['fuente']} | {texto}")


if __name__ == '__main__':
    print('Chunks indexados:', construir_indice())

    consultas = [
        'correo electrónico de Juan Pérez',
        'teléfono de María Torres',
        'cuánto tiempo guardan mis datos',
        'problemas con el internet que se corta',
        'cliente que no quiere publicidad',
        'familiares mencionados',
    ]
    for q in consultas:
        print(f"\n[Semántica] {q}")
        _mostrar(buscar_pii_vectorial(q, k=3))

    print('\n[Exacta] 72839102')
    _mostrar(buscar_exacta('72839102'))
