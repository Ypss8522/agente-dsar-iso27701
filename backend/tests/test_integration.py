import io
import json
import socket
from urllib.error import HTTPError, URLError

import pytest
from pypdf import PdfReader
from sqlalchemy import inspect

from dsar_api import create_app
from dsar_api.extensions import db
from dsar_api.models import AuditLog, DsarRequest, Submission
from dsar_api.api import intake
from tests.conftest import DPO, SERVICE

PAYLOAD = {'user_id': '72839102', 'email': 'juan@example.com', 'request_type': 'Acceso', 'details': 'Mi solicitud'}
KEY = 'submission-000000000001'
HEADERS = {'Idempotency-Key': KEY}


def test_serves_portal_and_panel_without_symlink(client):
    for path in ['/', '/dpo', '/static/main.js', '/static/dpo.js', '/static/styles.css']:
        assert client.get(path).status_code == 200
    assert b'DSAR-8921' not in client.get('/dpo').data


def test_public_intake_returns_only_ticket_and_deduplicates(client, app):
    first = client.post('/api/intake', json=PAYLOAD, headers=HEADERS)
    second = client.post('/api/intake', json={**PAYLOAD, 'timestamp': 'later'}, headers=HEADERS)
    assert first.status_code == second.status_code == 201
    assert first.json == second.json
    assert set(first.json['data']) == {'ticket_id'}
    assert first.headers['Cache-Control'] == 'no-store'
    with app.app_context():
        assert DsarRequest.query.count() == Submission.query.count() == 1
        assert AuditLog.query.filter_by(action='REQUEST_CREATED').count() == 1
    assert client.get('/api/requests').status_code == 401


def test_same_key_different_payload_is_rejected(client):
    assert client.post('/api/intake', json=PAYLOAD, headers=HEADERS).status_code == 201
    result = client.post('/api/intake', json={**PAYLOAD, 'details': 'Otra'}, headers=HEADERS)
    assert result.status_code == 409 and result.json['error']['code'] == 'idempotency_conflict'


@pytest.mark.parametrize('headers', [{}, {'Idempotency-Key': 'short'}, {**HEADERS, 'Origin': 'https://otro.example'}])
def test_intake_rejects_missing_key_and_other_origins(client, headers):
    assert client.post('/api/intake', json=PAYLOAD, headers=headers).status_code in (422, 403)


def test_invalid_input_and_missing_configuration(client, app):
    assert client.post('/api/intake', json={**PAYLOAD, 'request_type': 'invalido'}, headers=HEADERS).status_code == 422
    assert client.post('/api/intake', data='not json', content_type='application/json', headers=HEADERS).status_code == 400
    app.config['AUDIT_HASH_KEY'] = ''
    assert client.post('/api/intake', json=PAYLOAD, headers=HEADERS).status_code == 503


class Response:
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self, limit): return self.value


def configure_n8n(app, monkeypatch, handler):
    app.config.update(DSAR_INTAKE_MODE='n8n', N8N_WEBHOOK_TOKEN='private-token')
    class Opener:
        def open(self, req, timeout): return handler(req, timeout)
    monkeypatch.setattr(intake, 'build_opener', lambda *args: Opener())


def test_n8n_forwards_validated_payload_and_private_token(client, app, monkeypatch):
    def handler(req, timeout):
        assert req.headers['X-webhook-token'] == 'private-token'
        assert req.headers['Idempotency-key'] == KEY
        assert req.full_url == app.config['N8N_WEBHOOK_URL'] and timeout == 10
        forwarded = json.loads(req.data)
        created = client.post('/api/requests', json=forwarded, headers={**SERVICE, **HEADERS})
        return Response(json.dumps({'status': 'success', 'ticket_id': created.json['data']['ticket_id']}).encode())
    configure_n8n(app, monkeypatch, handler)
    result = client.post('/api/intake', json=PAYLOAD, headers=HEADERS)
    assert result.status_code == 201
    assert client.post('/api/intake', json=PAYLOAD, headers=HEADERS).json == result.json
    with app.app_context(): assert DsarRequest.query.count() == 1


@pytest.mark.parametrize('failure,status,code', [
    (URLError('refused'), 503, 'n8n_unreachable'),
    (ConnectionResetError('reset'), 503, 'n8n_unreachable'),
    (socket.timeout(), 504, 'n8n_timeout'),
    (HTTPError('http://local', 404, 'missing', {}, None), 502, 'n8n_http_error'),
    (b'not json', 502, 'n8n_invalid_response'),
    (b'{"status":"success","ticket_id":"DSAR-12345678"}', 502, 'n8n_invalid_response'),
    (b'{"status":"success"}', 502, 'n8n_invalid_response'),
])
def test_n8n_failures_never_create_fake_tickets(client, app, monkeypatch, failure, status, code):
    def handler(req, timeout):
        if isinstance(failure, Exception): raise failure
        return Response(failure)
    configure_n8n(app, monkeypatch, handler)
    result = client.post('/api/intake', json=PAYLOAD, headers=HEADERS)
    assert result.status_code == status and result.json['error']['code'] == code
    assert 'ticket_id' not in result.json
    with app.app_context(): assert DsarRequest.query.count() == 0


def test_pdf_requires_dpo_and_excludes_pii(client, app, seeded):
    ticket = client.post('/api/intake', json=PAYLOAD, headers=HEADERS).json['ticket_id']
    path = f'/api/requests/{ticket}/report.pdf'
    assert client.get(path).status_code == 401
    assert client.get(path, headers=SERVICE).status_code == 403
    response = client.get(path, headers=DPO)
    assert response.status_code == 200 and response.data.startswith(b'%PDF')
    text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(response.data)).pages)
    assert ticket in text and 'REQUEST_CREATED' in text
    assert not any(value in text for value in (PAYLOAD['user_id'], PAYLOAD['email'], PAYLOAD['details'], 'Juan Pérez'))
    with app.app_context(): assert AuditLog.query.filter_by(action='REPORT_GENERATED').count() == 1


def test_redaction_preserves_non_pii_and_audits_without_text(client, app):
    text = 'Juan Pérez DNI 72839102 correo juan@example.com teléfono +51 987654321 solicita acceso.'
    response = client.post('/api/redact', json={'text': text, 'values': ['Juan Pérez']}, headers=DPO)
    assert response.status_code == 200 and response.json['data']['review_required'] is True
    redacted = response.json['data']['text']
    assert 'solicita acceso' in redacted and redacted.count('[DATO OCULTO]') == 4
    with app.app_context(): assert text not in str(AuditLog.query.one().to_dict())
    assert client.post('/api/redact', json={'text': text}).status_code == 401
    assert client.post('/api/redact', json={'text': text, 'values': 'bad'}, headers=DPO).status_code == 422


def test_factory_reads_environment_again(monkeypatch):
    monkeypatch.setenv('DPO_API_KEY', 'key-one')
    one = create_app('development')
    monkeypatch.setenv('DPO_API_KEY', 'key-two')
    two = create_app('development')
    assert one.config['DPO_API_KEY'] == 'key-one'
    assert two.config['DPO_API_KEY'] == 'key-two'


def test_init_db_adds_idempotency_table_without_losing_data(client, app):
    client.post('/api/intake', json=PAYLOAD, headers=HEADERS)
    result = app.test_cli_runner().invoke(args=['init-db'])
    assert result.exit_code == 0
    with app.app_context():
        assert 'request_submissions' in inspect(db.engine).get_table_names()
        assert DsarRequest.query.count() == 1


def test_erasure_clears_early_requests_and_resolution_notes(client, app):
    ticket = client.post('/api/intake', json=PAYLOAD, headers=HEADERS).json['ticket_id']
    client.patch(f'/api/requests/{ticket}/status', json={'status':'En proceso', 'resolution_note':'Juan Pérez 72839102'}, headers=DPO)
    client.post('/api/users', json={'user_id':PAYLOAD['user_id'], 'nombre':'Juan Pérez'}, headers=SERVICE)
    assert client.post('/api/delete-user', json={'user_id':PAYLOAD['user_id']}, headers=DPO).status_code == 200
    with app.app_context():
        req = DsarRequest.query.one()
        assert req.subject_id is not None and req.document_id.startswith('ANON-')
        assert req.details is None and req.resolution_note is None


def test_retry_returns_committed_ticket_even_if_n8n_is_offline(client, app, monkeypatch):
    ticket = client.post('/api/intake', json=PAYLOAD, headers=HEADERS).json['ticket_id']
    def offline(req, timeout): raise AssertionError('El reintento no debe volver a llamar a n8n')
    configure_n8n(app, monkeypatch, offline)
    assert client.post('/api/intake', json=PAYLOAD, headers=HEADERS).json['ticket_id'] == ticket
