"""Genera configuración local e inicializa tablas, sin sobrescribir claves o datos."""
import argparse
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='Agregar dos titulares ficticios')
    args = parser.parse_args()
    from dotenv import dotenv_values, set_key
    env = ROOT / 'backend' / '.env'
    if not env.exists():
        env.write_text((ROOT / 'backend' / '.env.example').read_text(encoding='utf-8'), encoding='utf-8')
    if os.name != 'nt':
        env.chmod(0o600)
    existing = dotenv_values(env)
    for name in ('SERVICE_API_KEY', 'DPO_API_KEY', 'AUDIT_HASH_KEY', 'N8N_WEBHOOK_TOKEN'):
        if not existing.get(name) and not os.getenv(name):
            set_key(str(env), name, secrets.token_urlsafe(32))
    from dsar_api import create_app
    app = create_app()
    runner = app.test_cli_runner()
    for command in (['init-db', 'seed-demo'] if args.demo else ['init-db']):
        result = runner.invoke(args=[command])
        if result.exit_code:
            raise RuntimeError(f'Falló {command}: {result.output}') from result.exception
        print(result.output.strip())
    print('Configuración lista. Ejecuta: python app.py')
    print('Abre http://127.0.0.1:5000 y /dpo. La clave DPO está en backend/.env.')


if __name__ == '__main__':
    main()
