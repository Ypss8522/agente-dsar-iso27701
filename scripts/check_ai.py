"""Verificar modelo e índice con una búsqueda real, sin mostrar documentos."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'backend/.env')
    from ai_engine.search_engine import estado_ia, buscar_pii_vectorial
    status = estado_ia()
    if not status['ready']:
        print(status['message'], file=sys.stderr)
        return 1
    try:
        results = buscar_pii_vectorial('datos personales', k=1)
        if not results:
            raise RuntimeError('No se encontraron documentos.')
    except Exception:
        print('La IA no pudo completar la búsqueda de comprobación. Vuelve a preparar el modelo y el índice.', file=sys.stderr)
        return 1
    print(f"IA comprobada con el modelo real: {status['documents']} documentos, {status['chunks']} fragmentos.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
