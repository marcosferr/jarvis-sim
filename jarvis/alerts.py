"""Alert inbox: an HTTP endpoint that queues messages Jarvis phones the owner about.

  POST /alerta  {"mensaje": "Se cayó el servidor de ventas"}  Authorization: Bearer <JARVIS_ALERT_TOKEN>

Also takes the "message" / "msg" / "text" / "title" fields that Uptime Kuma, Grafana and friends send.
The serve loop drains the queue between incoming calls, so only one process ever drives the phone.
"""
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import ALERT_TOKEN, HTTP_HOST, HTTP_PORT
from .log import log

MAX_BODY = 4096
MAX_TEXT = 500        # it is read aloud: keep it short
MAX_QUEUE = 10
DEDUPE_SECONDS = 300  # a flapping monitor must not call 40 times
RETRY_SECONDS = 90
MAX_ATTEMPTS = 2

_lock = threading.Lock()
_queue = []   # [due_time, message, attempt]
_recent = {}  # message -> when it was last queued


def push(message):
    """Queue a message. Returns (accepted, status)."""
    now = time.time()
    with _lock:
        if now - _recent.get(message, 0) < DEDUPE_SECONDS:
            return False, "duplicada"
        if len(_queue) >= MAX_QUEUE:
            return False, "cola llena"
        _recent[message] = now
        _queue.append([now, message, 1])
    log("alert queued:", len(message), "chars")
    return True, "en cola"


def pop_due():
    """The oldest alert that is due, as (message, attempt), or None."""
    now = time.time()
    with _lock:
        due = [item for item in _queue if item[0] <= now]
        if not due:
            return None
        item = min(due)
        _queue.remove(item)
        return item[1], item[2]


def retry_later(message, attempt):
    if attempt >= MAX_ATTEMPTS:
        log("alert dropped after", attempt, "unanswered calls")
        return
    with _lock:
        _queue.append([time.time() + RETRY_SECONDS, message, attempt + 1])
    log(f"alert not answered, retrying in {RETRY_SECONDS} s")


def _text(payload):
    if isinstance(payload, dict):
        for key in ("mensaje", "message", "msg", "text", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:MAX_TEXT]
    return ""


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.split("?")[0].rstrip("/") != "/alerta":
            return self._reply(404, error="no existe")
        auth = self.headers.get("Authorization", "")
        if not hmac.compare_digest(auth.encode(), f"Bearer {ALERT_TOKEN}".encode()):
            return self._reply(401, error="token inválido")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if not 0 < length <= MAX_BODY:
            return self._reply(413, error=f"el cuerpo tiene que tener entre 1 y {MAX_BODY} bytes")
        try:
            payload = json.loads(self.rfile.read(length))
        except ValueError:
            return self._reply(400, error="JSON inválido")
        message = _text(payload)
        if not message:
            return self._reply(400, error='falta "mensaje"')
        accepted, status = push(message)
        self._reply(202 if accepted else 409 if status == "duplicada" else 429, estado=status)

    def _reply(self, code, **body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass  # only our own log lines, no request lines


def start_server():
    if len(ALERT_TOKEN) < 16:
        log("alert server off: set JARVIS_ALERT_TOKEN (16+ chars) in .env to enable POST /alerta")
        return None
    server = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log(f"alert server on http://{HTTP_HOST}:{HTTP_PORT}/alerta")
    return server
