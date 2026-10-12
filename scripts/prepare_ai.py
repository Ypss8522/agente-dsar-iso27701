"""Preparar el modelo y el índice fuera de HTTP, con opción totalmente local."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-model', type=Path, help='Modelo ya descargado; no usa Internet')
    args = parser.parse_args()
    from dotenv import load_dotenv, set_key
    env = ROOT / 'backend' / '.env'
    if not env.exists():
        print('Primero ejecuta python scripts/setup.py.', file=sys.stderr)
        return 1
    load_dotenv(env)
    try:
        from sentence_transformers import SentenceTransformer
        model_path = args.local_model.resolve() if args.local_model else ROOT / 'models_local' / 'embeddings'
        if args.local_model or (model_path / 'modules.json').exists():
            SentenceTransformer(str(model_path), device='cpu', local_files_only=True)
        else:
            SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', device='cpu').save(str(model_path))
        os.environ['EMBEDDING_MODEL'] = str(model_path)
        from ai_engine import search_engine
        search_engine.MODEL_NAME = str(model_path)
        count = search_engine.construir_indice()
        set_key(str(env), 'EMBEDDING_MODEL', str(model_path))
        print('Chunks indexados:', count)
        print('Reinicia Flask para cargar el modelo e índice locales.')
        return 0
    except Exception as error:
        print(f'No se pudo preparar el motor ({type(error).__name__}).', file=sys.stderr)
        print('Instala ai_engine/requirements.txt y verifica acceso a Hugging Face. Si usas un proxy SOCKS, instala httpx[socks].', file=sys.stderr)
        print('También puedes copiar un modelo ya descargado y usar --local-model RUTA. El resto de la app sigue disponible.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
