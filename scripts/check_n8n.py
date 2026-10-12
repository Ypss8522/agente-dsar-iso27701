"""Prueba optativa con n8n real, BD aislada y datos ficticios; no modifica tu n8n."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n8n-bin', default='n8n', help='Ruta al ejecutable n8n instalado')
    args = parser.parse_args()
    from dsar_api import create_app
    from werkzeug.serving import make_server
    app = create_app('testing')
    webhook_token = secrets.token_urlsafe(32)
    app.config.update(DSAR_INTAKE_MODE='n8n', N8N_WEBHOOK_TOKEN=webhook_token,
                      N8N_WEBHOOK_URL='http://127.0.0.1:5679/webhook/dsar-request')
    server = make_server('127.0.0.1', 5141, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    opener = build_opener(ProxyHandler({}))
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix='dsar-n8n-check-') as temp:
            directory = Path(temp)
            env = {**os.environ, 'N8N_USER_FOLDER':str(directory / 'home'), 'N8N_PORT':'5679',
                   'N8N_RUNNERS_BROKER_PORT':'5681', 'N8N_LISTEN_ADDRESS':'127.0.0.1', 'N8N_DIAGNOSTICS_ENABLED':'false',
                   'N8N_ENCRYPTION_KEY':secrets.token_hex(32), 'N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS':'true',
                   'EXECUTIONS_DATA_SAVE_ON_SUCCESS':'none', 'EXECUTIONS_DATA_SAVE_ON_ERROR':'none',
                   'EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS':'false'}
            credentials = [
                {'id':'dsarCheckWebhook', 'name':'DSAR Webhook', 'type':'httpHeaderAuth',
                 'data':{'name':'X-Webhook-Token','value':webhook_token}},
                {'id':'dsarCheckBackend', 'name':'DSAR Backend', 'type':'httpHeaderAuth',
                 'data':{'name':'X-API-Key','value':'test-service-key'}},
            ]
            workflow = json.loads((ROOT / 'n8n_workflows' / 'dsar-request.json').read_text())
            workflow.update(id='dsarCheckWorkflow', active=True)
            workflow['nodes'][0]['credentials']['httpHeaderAuth']['id'] = 'dsarCheckWebhook'
            workflow['nodes'][1]['credentials']['httpHeaderAuth']['id'] = 'dsarCheckBackend'
            workflow['nodes'][1]['parameters']['url'] = 'http://127.0.0.1:5141/api/requests'
            credentials_path, workflow_path = directory/'credentials.json', directory/'workflow.json'
            credentials_path.write_text(json.dumps(credentials))
            workflow_path.write_text(json.dumps(workflow))
            with (directory/'n8n.log').open('w+') as log:
                for command in (['import:credentials',f'--input={credentials_path}'],
                                ['import:workflow',f'--input={workflow_path}'],
                                ['publish:workflow','--id=dsarCheckWorkflow']):
                    result = subprocess.run([args.n8n_bin,*command],env=env,stdout=log,stderr=log,timeout=90)
                    if result.returncode:
                        log.flush(); log.seek(0)
                        print(log.read()[-3000:], file=sys.stderr)
                        raise RuntimeError('No se pudo importar la configuración de prueba en n8n.')
                process = subprocess.Popen([args.n8n_bin,'start'],env=env,stdout=log,stderr=log)
                ready = False
                for _ in range(120):
                    if process.poll() is not None: break
                    try:
                        with opener.open('http://127.0.0.1:5679/healthz',timeout=1) as response:
                            ready = response.status == 200
                    except (URLError, OSError): pass
                    if ready: break
                    time.sleep(0.25)
                if not ready:
                    log.flush(); log.seek(0); print(log.read()[-3000:],file=sys.stderr)
                    raise RuntimeError('n8n no alcanzó el estado listo.')
                payload={'user_id':'72839102','email':'demo@example.invalid','request_type':'Acceso'}
                headers={'Content-Type':'application/json','Idempotency-Key':'n8n-live-check-00001'}
                ticket=None
                for _ in range(120):
                    try:
                        with opener.open(Request('http://127.0.0.1:5141/api/intake',data=json.dumps(payload).encode(),headers=headers),timeout=15) as response:
                            result=json.load(response)
                        ticket=result['ticket_id']; break
                    except HTTPError as error:
                        body=json.load(error)
                        if body.get('error',{}).get('code')!='n8n_http_error' or 'HTTP 404' not in body.get('error',{}).get('message',''):
                            log.flush(); log.seek(0); print(log.read()[-3000:],file=sys.stderr)
                            raise RuntimeError(str(body))
                        time.sleep(0.25)
                if not ticket:
                    log.flush();log.seek(0);print(log.read()[-3000:],file=sys.stderr)
                    raise RuntimeError('El webhook publicado no devolvió el ticket.')
                with opener.open(Request('http://127.0.0.1:5141/api/intake',data=json.dumps(payload).encode(),headers=headers),timeout=15) as response:
                    assert json.load(response)['ticket_id']==ticket
                with app.app_context():
                    from dsar_api.models import DsarRequest
                    assert DsarRequest.query.count()==1
                # El webhook debe rechazar peticiones que carecen de su credencial.
                try:
                    opener.open(Request('http://127.0.0.1:5679/webhook/dsar-request',data=json.dumps(payload).encode(),headers=headers),timeout=5)
                    raise AssertionError('El webhook permitió una petición sin credencial.')
                except HTTPError as error: assert error.code==403 or error.code==401
                print('OK: Flask → n8n real → API Flask → ticket persistido; reintento sin duplicado y webhook autenticado.')
                process.terminate();process.wait(timeout=15);process=None
    finally:
        if process:
            process.terminate()
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired: process.kill();process.wait()
        server.shutdown()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
