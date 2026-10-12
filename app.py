"""Inicio desde la raíz: python app.py; reutiliza el backend del equipo."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'backend'))
from dsar_api import create_app  # noqa: E402

app = create_app()

if __name__ == '__main__':
    app.run(host=os.getenv('FLASK_HOST', '127.0.0.1'),
            port=int(os.getenv('FLASK_PORT', '5000')),
            debug=app.config.get('DEBUG', False) and os.getenv('FLASK_DEBUG', '1') != '0',
            use_reloader=os.getenv('FLASK_USE_RELOADER', '1') == '1')
