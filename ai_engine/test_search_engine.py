"""Pruebas sin descargas; FAISS real cuando está instalado."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_engine import search_engine as engine


class ValidationTests(unittest.TestCase):
    def test_invalid_queries_and_k(self):
        for query, k in [(None, 5), (' ', 5), ('x' * 4001, 5), ('datos', True),
                         ('datos', 0), ('datos', 51), ('datos', '5')]:
            with self.subTest(k=k), self.assertRaises(ValueError):
                engine.buscar_pii_vectorial(query, k)

    def test_model_identity_survives_directory_change(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'a', Path(directory) / 'b'
            first.mkdir(); second.mkdir()
            for root in (first, second):
                (root / 'config.json').write_text('{"dimension":2}')
                (root / 'model.safetensors').write_bytes(b'fake-test-weights')
            self.assertEqual(engine._model_identity(str(first)), engine._model_identity(str(second)))
            (second / 'model.safetensors').write_bytes(b'different-weights')
            engine._model_identity.cache_clear()
            self.assertNotEqual(engine._model_identity(str(first)), engine._model_identity(str(second)))

    def test_query_is_trimmed(self):
        self.assertEqual(engine.validar_consulta(' datos '), 'datos')

    def test_chunking_preserves_overlap(self):
        self.assertEqual(engine._dividir('abcdefghij', tam=6, solape=2), ['abcdef', 'efghij', 'ij'])

    def test_exact_search_uses_complete_terms(self):
        chunks = [{'texto': 'DNI 12345 y 9123456', 'fuente': 'demo.txt'}]
        with patch.object(engine, '_asegurar_indice'), patch.object(engine, '_chunks', chunks):
            self.assertEqual(len(engine.buscar_exacta('12345')), 1)
            self.assertEqual(engine.buscar_exacta('1234'), [])


VECTOR_DEPS = all(importlib.util.find_spec(name) for name in ('faiss', 'numpy'))


@unittest.skipUnless(VECTOR_DEPS, 'FAISS y NumPy no están instalados')
class IntegrationTests(unittest.TestCase):
    def test_build_reload_and_search_real_faiss(self):
        import numpy as np

        class Encoder:
            def get_sentence_embedding_dimension(self):
                return 2

            def encode(self, texts, **kwargs):
                return np.array([[1, 0] if 'acceso' in text else [0, 1] for text in texts])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / 'documentos'
            docs.mkdir()
            (docs / 'acceso.txt').write_text('acceso a datos', encoding='utf-8')
            (docs / 'borrado.txt').write_text('borrar cuenta', encoding='utf-8')
            with patch.multiple(engine, DOCS_DIR=str(docs), DATA_DIR=directory,
                                INDEX_PATH=str(root / 'index'), META_PATH=str(root / 'metadata.json'),
                                _model=Encoder(), _index=None, _chunks=[]):
                self.assertEqual(engine.construir_indice(), 2)
                engine._index = None
                results = engine.buscar_pii_vectorial('acceso', 5)
                self.assertEqual(len(results), 2)
                self.assertEqual(results[0]['fuente'], 'acceso.txt')
                self.assertEqual(results[0]['score'], 1.0)
                json.dumps(results, allow_nan=False)
                engine._index = None
                with patch.object(engine, 'MODEL_NAME', 'otro-modelo'):
                    with self.assertRaises(engine.SearchUnavailable):
                        engine.buscar_pii_vectorial('acceso')


if __name__ == '__main__':
    unittest.main()
