"""Preparar la IA local y abrir el agente DSAR con un solo comando."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, check=True)


def prepare_dependencies(skip_install=False):
    names = ('flask', 'flask_sqlalchemy', 'flask_cors', 'dotenv', 'reportlab',
             'torch', 'sentence_transformers', 'faiss', 'numpy', 'pypdf')
    missing = [name for name in names if importlib.util.find_spec(name) is None]
    digest = hashlib.sha256(b''.join((ROOT / p).read_bytes() for p in
        ('backend/requirements.txt', 'ai_engine/requirements.txt'))).hexdigest()
    stamp = Path(sys.prefix) / '.dsar-dependencies'
    if skip_install:
        if missing:
            raise RuntimeError('Faltan dependencias: ' + ', '.join(missing))
        return
    if not missing and stamp.exists() and stamp.read_text() == digest:
        print('Dependencias ya preparadas.', flush=True)
        return
    print('Instalando dependencias. La primera vez requiere Internet y puede tardar.', flush=True)
    run('-m', 'pip', 'install', '--upgrade', 'pip')
    run('-m', 'pip', 'install', '-r', ROOT / 'backend/requirements.txt')
    if importlib.util.find_spec('torch') is None:
        run('-m', 'pip', 'install', 'torch', '--index-url', 'https://download.pytorch.org/whl/cpu')
    run('-m', 'pip', 'install', '-r', ROOT / 'ai_engine/requirements.txt')
    stamp.write_text(digest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='Agregar titulares ficticios')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--no-browser', action='store_true', help='No abrir el navegador')
    parser.add_argument('--solo-preparar', action='store_true', help='Preparar y verificar IA sin arrancar Flask')
    parser.add_argument('--usar-entorno-actual', action='store_true', help='Usar el Python actual en lugar de .venv')
    parser.add_argument('--sin-instalar', action='store_true', help='Comprobar dependencias existentes sin instalar')
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error('Se necesita Python 3.11 o superior.')
    if not 1 <= args.port <= 65535:
        parser.error('El puerto debe estar entre 1 y 65535.')
    if not args.solo_preparar:
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', args.port))
            except OSError:
                print(f'El puerto {args.port} está ocupado. Detén Flask con Ctrl+C en su terminal y vuelve a iniciar.', file=sys.stderr)
                return 1
    env = ROOT / '.venv'
    if not args.usar_entorno_actual and Path(sys.prefix).resolve() != env.resolve():
        python = env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not python.exists():
            print('Creando entorno virtual del proyecto...', flush=True)
            try:
                venv.EnvBuilder(with_pip=True).create(env)
            except Exception:
                print('No se pudo crear .venv. En Linux Mint instala: sudo apt install python3-venv', file=sys.stderr)
                return 1
        try:
            return subprocess.call([str(python), str(Path(__file__).resolve()), *sys.argv[1:]], cwd=ROOT)
        except KeyboardInterrupt:
            return 0
    try:
        prepare_dependencies(args.sin_instalar)
        run(ROOT / 'scripts/setup.py', *(['--demo'] if args.demo else []))
        from dotenv import load_dotenv, dotenv_values
        load_dotenv(ROOT / 'backend/.env')
        print('Preparando el modelo local y actualizando los documentos...', flush=True)
        configured_model = os.getenv('EMBEDDING_MODEL')
        model_args = ['--local-model', configured_model] if configured_model and Path(configured_model).is_dir() else []
        run(ROOT / 'scripts/prepare_ai.py', *model_args)
        os.environ['EMBEDDING_MODEL'] = dotenv_values(ROOT / 'backend/.env')['EMBEDDING_MODEL']
        run(ROOT / 'scripts/check_ai.py')
        if args.solo_preparar:
            return 0
        url = f'http://127.0.0.1:{args.port}'
        print(f'Portal del titular: {url}\nPanel DPO: {url}/dpo', flush=True)
        # La clave sólo se muestra en una terminal interactiva local, nunca en
        # logs de CI, enlaces, historial del navegador o archivos frontend.
        if sys.stdout.isatty():
            key = os.getenv('DPO_API_KEY') or dotenv_values(ROOT / 'backend/.env').get('DPO_API_KEY')
            print(f'Clave para conectar al panel DPO (cópiala allí): {key}', flush=True)
        else:
            print('La clave DPO está en backend/.env.', flush=True)
        child_env = {**os.environ, 'FLASK_HOST': '127.0.0.1', 'FLASK_PORT': str(args.port),
                     'FLASK_USE_RELOADER': '0', 'FLASK_DEBUG': '0'}
        process = subprocess.Popen([sys.executable, str(ROOT / 'app.py')], cwd=ROOT, env=child_env)
        try:
            opener = build_opener(ProxyHandler({}))
            for _ in range(60):
                if process.poll() is not None:
                    raise RuntimeError('Flask terminó antes de abrir el portal.')
                try:
                    with opener.open(url + '/api/health', timeout=1) as response:
                        if response.status == 200:
                            if not args.no_browser:
                                webbrowser.open(url + '/dpo')
                            break
                except (URLError, OSError):
                    time.sleep(0.5)
            else:
                raise RuntimeError('Flask no quedó disponible. Revisa la salida de esta terminal.')
            print('Proyecto listo. Mantén esta terminal abierta; Ctrl+C para detener.', flush=True)
            return process.wait()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    except KeyboardInterrupt:
        print('\nProyecto detenido.')
        return 0
    except (subprocess.CalledProcessError, RuntimeError, OSError) as error:
        print(f'No se pudo completar el inicio: {error}', file=sys.stderr)
        print('Conserva los archivos existentes y comparte el error de este paso, sin incluir las claves.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
