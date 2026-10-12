"""Errores de arranque deben detenerse antes de instalar o tocar datos."""
import socket
from unittest.mock import patch

import pytest

import iniciar


def test_busy_port_does_not_prepare_or_install(capsys):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); listener.listen()
        port = listener.getsockname()[1]
        with patch('sys.argv', ['iniciar.py', '--port', str(port)]), patch.object(iniciar, 'prepare_dependencies') as prepare:
            assert iniciar.main() == 1
            prepare.assert_not_called()
    assert 'ocupado' in capsys.readouterr().err


def test_skip_install_reports_missing_dependencies_without_pip():
    with patch.object(iniciar.importlib.util, 'find_spec', return_value=None), patch.object(iniciar, 'run') as run:
        with pytest.raises(RuntimeError, match='Faltan dependencias'):
            iniciar.prepare_dependencies(skip_install=True)
        run.assert_not_called()


def test_invalid_port_is_rejected_before_environment_setup():
    with patch('sys.argv', ['iniciar.py', '--port', '0']), patch.object(iniciar.venv.EnvBuilder, 'create') as create:
        with pytest.raises(SystemExit):
            iniciar.main()
        create.assert_not_called()
