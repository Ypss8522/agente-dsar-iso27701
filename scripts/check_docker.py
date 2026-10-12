"""Prueba de arranque del Compose aislado de CI; registra un ticket ficticio."""
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener
import uuid

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:5000'
OPENER = build_opener(ProxyHandler({}))


def request(url, *, payload=None, headers=None):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    combined = {'Content-Type': 'application/json', **(headers or {})}
    with OPENER.open(Request(url, data=data, headers=combined), timeout=5) as response:
        return response.status, response.read()


def wait_for(url):
    for _ in range(90):
        try:
            status, _ = request(url)
            if status == 200:
                return
        except (URLError, OSError):
            pass
        time.sleep(1)
    raise RuntimeError(f'El servicio no quedó disponible: {url}')


def main():
    config = dotenv_values(ROOT / 'backend' / '.env')
    dpo_key = config.get('DPO_API_KEY')
    if not dpo_key or config.get('DSAR_INTAKE_MODE', 'direct') != 'direct':
        raise RuntimeError('Esta prueba requiere el .env de CI en modo directo.')
    wait_for(BASE + '/api/health')
    wait_for('http://127.0.0.1:5678/healthz')
    assert json.loads(request(BASE + '/api/health')[1])['data']['database'] == 'up'
    for route in ('/', '/dpo'):
        assert b'<!doctype html' in request(BASE + route)[1].lower()
    try:
        request(BASE + '/api/requests')
    except HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError('La API privada aceptó una petición sin credencial.')
    payload = {'user_id': '72839102', 'email': 'ci@example.invalid',
               'request_type': 'Acceso', 'details': 'Prueba ficticia de Compose'}
    headers = {'Idempotency-Key': str(uuid.uuid4())}
    first = json.loads(request(BASE + '/api/intake', payload=payload, headers=headers)[1])
    retry = json.loads(request(BASE + '/api/intake', payload=payload, headers=headers)[1])
    ticket = first['ticket_id']
    assert ticket == retry['ticket_id']
    dpo = {'X-API-Key': dpo_key}
    result = json.loads(request(BASE + '/api/requests/' + ticket, headers=dpo)[1])
    assert result['data']['ticket_id'] == ticket
    assert request(BASE + '/api/requests/' + ticket + '/report.pdf', headers=dpo)[1].startswith(b'%PDF-')
    print('Compose verificado: Flask/Gunicorn, SQLite, portal, DPO, autenticación, ticket, reintento, PDF y n8n disponible.')
    print('Esta prueba no importa el workflow ni descarga un modelo de IA.')


if __name__ == '__main__':
    main()
