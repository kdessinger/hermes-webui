"""Site-local shared app slots. Invoked only after the WebUI auth/CSRF gate.

Not generic extension storage: only three app slots, no credentials, no arbitrary
filesystem paths, no server fetching of configured URLs. State belongs to this
WebUI installation (which currently has one authenticated owner), not a chat.
"""
import json
import os
import tempfile
import threading
from urllib.parse import urlsplit

from api.config import STATE_DIR

DEFAULTS = {
    'external-app-tab': {'url': '/apps/nas-recovery/', 'label': 'NAS Recovery'},
    'external-app-tab-2': {'url': '/apps/opencve/', 'label': 'OpenCVE'},
    'external-app-tab-3': {'url': '', 'label': 'App 3'},
}
_LOCK = threading.RLock()


def _validate(value):
    if not isinstance(value, dict):
        raise ValueError('Expected app configuration')
    url, label = value.get('url'), value.get('label')
    if not isinstance(url, str) or not isinstance(label, str):
        raise ValueError('URL and label must be text')
    if len(url) > 2048 or not 1 <= len(label.strip()) <= 24:
        raise ValueError('Label must be 1–24 characters; URL limit is 2048')
    if any(ord(c) < 32 or ord(c) == 127 for c in url + label) or '\\' in url:
        raise ValueError('Invalid control characters')
    if url and url not in ('/apps/nas-recovery/', '/apps/opencve/'):
        u = urlsplit(url)
        if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password or any(c.isspace() for c in url):
            raise ValueError('Use an http(s) URL without credentials, or a built-in app path')
        # Validate malformed/out-of-range ports as well.
        _ = u.port
    return {'url': url, 'label': label.strip()}


def _load():
    result = {k: dict(v) for k, v in DEFAULTS.items()}
    try:
        raw = json.loads((STATE_DIR / 'external-apps.json').read_text())
    except FileNotFoundError:
        return result
    if not isinstance(raw, dict) or set(raw) - set(DEFAULTS):
        raise ValueError('Invalid stored app configuration')
    for key, value in raw.items():
        result[key] = _validate(value)
    return result


def _save(apps):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.external-apps-', dir=STATE_DIR)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(apps, f, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, STATE_DIR / 'external-apps.json')
    finally:
        if os.path.exists(name):
            os.unlink(name)


def handle_external_apps(handler, parsed):
    if parsed.path != '/api/external-apps':
        return False

    def reply(status, data):
        body = json.dumps(data).encode()
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json')
        handler.send_header('Content-Length', str(len(body)))
        handler.send_header('Cache-Control', 'no-store')
        handler.end_headers()
        handler.wfile.write(body)
        return True

    if handler.command not in ('GET', 'POST'):
        return reply(405, {'error': 'Method not supported'})
    update = None
    if handler.command == 'POST':
        try:
            if handler.headers.get('Transfer-Encoding'):
                raise ValueError('Transfer encoding not supported')
            length = int(handler.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192:
                raise ValueError('Invalid request size')
            if handler.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                raise ValueError('Expected application/json')
            raw = json.loads(handler.rfile.read(length))
            if not isinstance(raw, dict) or not isinstance(raw.get('id'), str) or raw['id'] not in DEFAULTS:
                raise ValueError('Unknown app slot')
            update = (raw['id'], _validate(raw))
        except (ValueError, TypeError, UnicodeError):
            return reply(400, {'error': 'Invalid app configuration'})
    try:
        with _LOCK:
            apps = _load()
            if update:
                apps[update[0]] = update[1]
                _save(apps)
        return reply(200, apps)
    except (OSError, ValueError):
        return reply(503, {'error': 'App settings unavailable; nothing was saved. Retry later.'})
