"""Standard-library worker sent to an authenticated remote GPU host by RemoteClient."""
import base64
import json
import re
import signal
import sys
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

ENDPOINTS = {'/v1/models', '/v1/systemone', '/health', '/openjev/identity', '/v1/chat/completions'}
MAX_FRAME = 2 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Model redirects are not allowed')


def serve(session, identity_file):
    # Some remote tools supply a PTY even when the local CLI uses pipes. Raw mode
    # prevents input echo and the terminal's 4096-byte canonical line truncation.
    if sys.stdin.isatty():
        import tty
        tty.setraw(sys.stdin.fileno())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    print('OPENJEV_READY ' + session, flush=True)
    # Reap orphan workers when a remote transport drops without delivering EOF.
    # The client sends health checks while connected, including when the UI is idle.
    while True:
        signal.alarm(60)
        line = sys.stdin.buffer.readline(MAX_FRAME + 1)
        signal.alarm(0)
        if not line or line == b'OPENJEV_CLOSE\n':
            return
        if len(line) > MAX_FRAME or not line.endswith(b'\n'):
            return
        match = re.fullmatch(rb'OPENJEV_CALL ([a-f0-9]{32}) ([A-Za-z0-9+/=]+)\n', line)
        if not match:
            return
        request_id, encoded = match.groups()
        started = time.monotonic()
        try:
            payload = json.loads(zlib.decompress(base64.b64decode(encoded, validate=True)))
            path = payload['path']
            if path not in ENDPOINTS:
                raise ValueError('Unsupported endpoint')
            if path == '/openjev/identity':
                body = json.loads(Path(identity_file).read_text())
                result = {'status': 200, 'body': body}
            else:
                data = json.dumps(payload['body'], ensure_ascii=False).encode() if payload['body'] is not None else None
                request = urllib.request.Request('http://127.0.0.1:8080' + path, data=data,
                                                 headers={'Content-Type': 'application/json'})
                with opener.open(request, timeout=180) as response:
                    result = {'status': response.status, 'body': json.load(response)}
        except urllib.error.HTTPError as exc:
            try:
                body = json.load(exc)
            except ValueError:
                body = {'detail': 'The model rejected this request'}
            result = {'status': exc.code, 'body': body}
        except Exception as exc:
            result = {'status': 503, 'body': {'detail': type(exc).__name__ + ': model service unavailable'}}
        result['inference_ms'] = round((time.monotonic() - started) * 1000, 1)
        reply = base64.b64encode(json.dumps(result).encode()).decode()
        print('OPENJEV_RPC ' + request_id.decode() + ' ' + reply, flush=True)


if __name__ == '__main__':
    serve(sys.argv[1], sys.argv[2])
