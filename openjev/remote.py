"""Persistent, authenticated HTTP relay through the user's remote command session."""
import base64
import json
import os
import re
from pathlib import Path
import select
import shlex
import subprocess
import threading
import time
import uuid
import zlib

from .relay_worker import ENDPOINTS, MAX_FRAME


class RemoteUnavailable(RuntimeError):
    pass


class RemoteHTTPError(RemoteUnavailable):
    """An upstream HTTP rejection whose status must be preserved by the adapter."""

    def __init__(self, status_code, body):
        self.status_code, self.body = status_code, body
        super().__init__(f'Remote model service returned HTTP {status_code}')


class RemoteClient:
    def __init__(self, command, identity_file='/data/openjev/status.json', connect_timeout=30, request_timeout=220, keepalive_interval=15):
        if not isinstance(command, list) or not command or any(not isinstance(s, str) or not s for s in command):
            raise ValueError('OPENJEV_RELAY_COMMAND must be a nonempty JSON array of command arguments')
        self.command = command
        self.identity_file = identity_file
        self.connect_timeout, self.request_timeout = connect_timeout, request_timeout
        self._process = None
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._closed = False
        self._stop = threading.Event()
        self._keepalive_interval = keepalive_interval
        self._maintenance = threading.Thread(target=self._keepalive, daemon=True)
        self._maintenance.start()

    def _disconnect(self, graceful=False):
        process, self._process = self._process, None
        self._buffer.clear()
        if process is not None:
            if process.poll() is None and graceful:
                try:
                    os.write(process.stdin.fileno(), b"OPENJEV_CLOSE\n")
                    process.wait(timeout=1)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdin.close()
            process.stdout.close()

    def close(self):
        self._stop.set()
        with self._lock:
            self._closed = True
            self._disconnect(graceful=True)
        self._maintenance.join(timeout=2)

    def _keepalive(self):
        while not self._stop.wait(self._keepalive_interval):
            if not self._lock.acquire(blocking=False):
                continue
            try:
                if self._process is not None:
                    try:
                        self._exchange("/health", None, timeout=8)
                    except (OSError, EOFError, TimeoutError, ValueError, RemoteUnavailable):
                        self._disconnect()
            finally:
                self._lock.release()

    def _line(self, deadline):
        while b'\n' not in self._buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self._process.stdout], [], [], remaining)[0]:
                raise TimeoutError('Remote response timed out')
            chunk = os.read(self._process.stdout.fileno(), 65536)
            if not chunk:
                raise EOFError('Remote session ended')
            self._buffer.extend(chunk)
            if len(self._buffer) > MAX_FRAME:
                raise RemoteUnavailable('Invalid oversized response from the remote relay')
        line, _, rest = self._buffer.partition(b'\n')
        self._buffer = rest
        return line.rstrip(b'\r')

    def _connect(self):
        self._disconnect()
        session = uuid.uuid4().hex
        code = Path(__file__).with_name('relay_worker.py').read_text()
        command = self.command + ['python3 -u -c ' + shlex.quote(code) + ' ' + shlex.quote(session)
                                  + ' ' + shlex.quote(self.identity_file)]
        self._process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, bufsize=0,
                                         env=dict(os.environ, COLUMNS='2000'))
        os.set_blocking(self._process.stdin.fileno(), False)
        deadline = time.monotonic() + self.connect_timeout
        while ('OPENJEV_READY ' + session).encode() not in self._line(deadline):
            pass  # Ignore remote command status messages; never return them as model output.

    def _write(self, frame, deadline):
        remaining_frame = memoryview(frame)
        while remaining_frame:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [self._process.stdin], [], remaining)[1]:
                raise TimeoutError('Remote request timed out')
            try:
                written = os.write(self._process.stdin.fileno(), remaining_frame)
            except BlockingIOError:
                continue
            if written == 0:
                raise EOFError('Remote session ended')
            remaining_frame = remaining_frame[written:]

    def _exchange(self, path, body, timeout):
        encoded = base64.b64encode(zlib.compress(json.dumps(dict(path=path, body=body), ensure_ascii=False).encode()))
        request_id = uuid.uuid4().hex.encode()
        frame = b'OPENJEV_CALL ' + request_id + b' ' + encoded + b'\n'
        if len(frame) > MAX_FRAME:
            from .engine import InputTooLong
            raise InputTooLong('This request exceeds the remote relay size limit; shorten the state or questions')
        deadline = time.monotonic() + timeout
        self._write(frame, deadline)
        while True:
            line = self._line(deadline)
            match = re.search(rb'OPENJEV_RPC ([a-f0-9]{32}) ([A-Za-z0-9+/=]+)', line)
            if match:
                if match[1] != request_id:
                    raise RemoteUnavailable('Mismatched response from the remote relay')
                result = json.loads(base64.b64decode(match[2], validate=True))
                if not isinstance(result, dict) or 'status' not in result or 'body' not in result:
                    raise RemoteUnavailable('Invalid response from the remote relay')
                return result

    def request(self, path, body=None):
        if path not in ENDPOINTS:
            raise ValueError('Unsupported remote relay endpoint')
        if not self._lock.acquire(timeout=self.request_timeout):
            raise RemoteUnavailable('Remote connection is busy; try again after the current request')
        try:
            if self._closed:
                raise RemoteUnavailable('The remote connection is closed')
            try:
                if self._process is None or self._process.poll() is not None:
                    self._connect()
                result = self._exchange(path, body, self.request_timeout)
            except (OSError, EOFError, TimeoutError, ValueError, RemoteUnavailable) as exc:
                self._disconnect()
                # Never replay a request after an uncertain connection failure.
                # The following user request will open a fresh authenticated session.
                raise RemoteUnavailable('Remote connection interrupted; check the model service and remote login, then try again') from exc
            code, response = result['status'], result['body']
            if path == '/v1/chat/completions' and code != 200:
                raise RemoteHTTPError(code, response)
            if code in (400, 422):
                from .engine import InputTooLong
                detail = response.get('detail', 'The model rejected this request') if isinstance(response, dict) else 'The model rejected this request'
                raise InputTooLong(str(detail))
            if code != 200 or not isinstance(response, dict):
                raise RemoteUnavailable(f'Remote model service unavailable (HTTP {code})')
            if path == '/v1/systemone':
                response['_inference_ms'] = result.get('inference_ms')
            return response
        finally:
            self._lock.release()
