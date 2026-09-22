import json
import secrets
import shlex
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from openjev.engine import InputTooLong
from openjev.remote import RemoteClient, RemoteUnavailable


@pytest.fixture
def relay(monkeypatch, tmp_path):
    received, processes, commands = [], [], []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append(body)
            if body.get('delay'):
                time.sleep(body['delay'])
            self.send_response(body.get('status', 200)); self.end_headers()
            try:
                self.wfile.write(json.dumps({'echo': body, 'detail': 'rejected'}).encode())
            except BrokenPipeError:
                pass
        def do_GET(self):
            self.send_response(200); self.end_headers()
            self.wfile.write(b'{"models":[{"name":"openjev-latest"}]}')
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    identity = tmp_path/'identity.json'; identity.write_text('{"phase":"ready"}')
    real_popen = subprocess.Popen
    def execute(command, **kwargs):
        commands.append(command)
        args = shlex.split(command[-1])
        args[0] = sys.executable
        args[3] = args[3].replace('http://127.0.0.1:8080', f'http://127.0.0.1:{server.server_port}')
        process = real_popen(args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr('openjev.remote.subprocess.Popen', execute)
    client = RemoteClient(['ssh', 'test-gpu'], str(identity), connect_timeout=2, request_timeout=2)
    try:
        yield client, received, processes, commands
    finally:
        client.close()
        server.shutdown(); server.server_close(); thread.join()


def test_reuses_authenticated_process_with_large_unicode_payload(relay):
    client, received, processes, commands = relay
    body = {'state': "退款 ' $(touch /tmp/never-executed) " + secrets.token_hex(60000)}
    assert client.request('/v1/models')['models']
    result = client.request('/v1/systemone', body)
    assert result['echo'] == body
    assert result['_inference_ms'] >= 0
    assert client.request('/openjev/identity') == {'phase': 'ready'}
    assert received == [body]
    assert len(processes) == 1
    assert commands[0][:2] == ['ssh', 'test-gpu']
    assert body['state'] not in commands[0][-1]
    client.close()
    assert processes[0].poll() is not None
    with pytest.raises(RemoteUnavailable, match='closed'):
        client.request('/health')


@pytest.mark.parametrize('status,exception', [(422, InputTooLong), (503, RemoteUnavailable)])
def test_http_errors_preserve_connection_and_are_not_decisions(relay, status, exception):
    client, _, processes, _ = relay
    with pytest.raises(exception):
        client.request('/v1/systemone', {'status': status})
    assert client.request('/v1/models')['models']
    assert len(processes) == 1


def test_concurrent_requests_cannot_receive_each_others_response(relay):
    client, received, processes, _ = relay
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda i: client.request('/v1/systemone', {'i': i})['echo']['i'], range(12)))
    assert results == list(range(12))
    assert len(received) == 12 and len(processes) == 1


def test_dead_connection_reopens_before_new_request(relay):
    client, _, processes, _ = relay
    client.request('/v1/models')
    processes[0].terminate(); processes[0].wait(timeout=2)
    assert client.request('/v1/models')['models']
    assert len(processes) == 2


def test_timeout_does_not_replay_post_and_next_request_recovers(relay):
    client, received, processes, _ = relay
    client.request('/v1/models')
    client.request_timeout = .05
    with pytest.raises(RemoteUnavailable, match='interrupted'):
        client.request('/v1/systemone', {'delay': .2})
    assert len(received) == 1 and len(processes) == 1
    assert processes[0].poll() is not None
    client.request_timeout = 2
    assert client.request('/v1/systemone', {'i': 2})['echo']['i'] == 2
    assert len(received) == 2 and len(processes) == 2


def test_login_failure_returns_explicit_error(monkeypatch):
    real_popen = subprocess.Popen
    monkeypatch.setattr('openjev.remote.subprocess.Popen', lambda command, **kwargs:
                        real_popen([sys.executable, '-c', 'print("Login required")'], **kwargs))
    client = RemoteClient(['ssh', 'test-gpu'], connect_timeout=1)
    with pytest.raises(RemoteUnavailable, match='remote login'):
        client.request('/health')
    assert client._process is None
    client.close()


def test_command_and_endpoint_validation():
    for command in ([], 'ssh host', [1], ['']):
        with pytest.raises(ValueError):
            RemoteClient(command)
    with pytest.raises(ValueError):
        RemoteClient(['ssh', 'test-gpu']).request('https://example.com')


def test_cli_terminal_control_prefix_does_not_hide_rpc(relay, monkeypatch):
    client, _, _, _ = relay
    original = client._line
    monkeypatch.setattr(client, '_line', lambda deadline: b'\x1b[2K\rConnected\r' + original(deadline))
    assert client.request('/v1/models')['models']
    assert client.request('/v1/systemone', {'state': 'x'})['echo']['state'] == 'x'


def test_idle_maintenance_detects_dead_worker_before_next_request(relay):
    client, _, processes, _ = relay
    client._keepalive_interval = .02
    # Wake/recreate the maintenance thread with the short test interval.
    client._stop.set(); client._maintenance.join(timeout=2)
    client._stop.clear()
    client._maintenance = threading.Thread(target=client._keepalive, daemon=True)
    client._maintenance.start()
    client.request('/v1/models')
    processes[0].terminate(); processes[0].wait(timeout=2)
    deadline = time.monotonic()+2
    while client._process is not None and time.monotonic() < deadline:
        time.sleep(.01)
    assert client._process is None
    assert client.request('/v1/models')['models']
