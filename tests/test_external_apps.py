"""Site app configuration is durable, isolated by slot, and never a proxy target."""
import importlib
import json
from io import BytesIO
from urllib.parse import urlsplit

import pytest


class Handler:
    def __init__(self, method='GET', body=None):
        self.command = method
        raw = json.dumps(body).encode() if body is not None else b''
        self.headers = {'Content-Length': str(len(raw)), 'Content-Type': 'application/json'}
        self.rfile = BytesIO(raw)
        self.wfile = BytesIO()
        self.sent = {}
    def send_response(self, status): self.status = status
    def send_header(self, k, v): self.sent[k] = v
    def end_headers(self): pass


def api(tmp_path, monkeypatch):
    from api import external_apps
    monkeypatch.setattr(external_apps, 'STATE_DIR', tmp_path)
    return external_apps


def request(module, method='GET', body=None):
    h = Handler(method, body)
    assert module.handle_external_apps(h, urlsplit('/api/external-apps'))
    return h.status, json.loads(h.wfile.getvalue())


def test_defaults_and_cross_client_persistence(tmp_path, monkeypatch):
    mod = api(tmp_path, monkeypatch)
    status, apps = request(mod)
    assert status == 200
    assert apps['external-app-tab'] == {'url': '/apps/nas-recovery/', 'label': 'NAS Recovery'}
    assert apps['external-app-tab-2'] == {'url': '/apps/opencve/', 'label': 'OpenCVE'}
    update = {'id': 'external-app-tab', 'url': 'https://example.org/dashboard', 'label': 'My app'}
    assert request(mod, 'POST', update)[0] == 200
    # A fresh module/process has no browser storage or in-memory configuration.
    mod = importlib.reload(mod)
    monkeypatch.setattr(mod, 'STATE_DIR', tmp_path)
    status, restored = request(mod)
    assert restored[update['id']] == {k: update[k] for k in ('url', 'label')}
    assert restored['external-app-tab-2'] == apps['external-app-tab-2']
    assert (tmp_path / 'external-apps.json').stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('url', ['javascript:alert(1)', '//evil.test', '/api/auth', 'https://u:p@example.org', 'https://example.org/\nfoo'])
def test_invalid_urls_do_not_write(tmp_path, monkeypatch, url):
    mod = api(tmp_path, monkeypatch)
    assert request(mod, 'POST', {'id': 'external-app-tab', 'url': url, 'label': 'App'})[0] == 400
    assert not (tmp_path / 'external-apps.json').exists()


def test_third_slot_preserves_existing_apps(tmp_path, monkeypatch):
    mod = api(tmp_path, monkeypatch)
    before = request(mod)[1]
    assert before['external-app-tab-3'] == {'url': '', 'label': 'App 3'}
    update = {'id': 'external-app-tab-3', 'url': 'https://example.org/third', 'label': 'Third app'}
    assert request(mod, 'POST', update)[0] == 200
    restored = request(mod)[1]
    assert restored['external-app-tab-3'] == {'url': update['url'], 'label': update['label']}
    for slot in ('external-app-tab', 'external-app-tab-2'):
        assert restored[slot] == before[slot]


def test_bad_slot_and_method(tmp_path, monkeypatch):
    mod = api(tmp_path, monkeypatch)
    assert request(mod, 'POST', {'id': '../auth', 'url': '', 'label': 'App'})[0] == 400
    assert request(mod, 'DELETE')[0] == 405
    assert mod.handle_external_apps(Handler(), urlsplit('/api/elsewhere')) is False


def test_persistence_failure_is_not_success(tmp_path, monkeypatch):
    mod = api(tmp_path, monkeypatch)
    def fail(*args, **kwargs): raise OSError('fixture failure')
    monkeypatch.setattr(mod.os, 'replace', fail)
    assert request(mod, 'POST', {'id': 'external-app-tab', 'url': '', 'label': 'App'})[0] == 503


def test_corrupt_state_is_not_silently_overwritten(tmp_path, monkeypatch):
    mod = api(tmp_path, monkeypatch)
    (tmp_path / 'external-apps.json').write_text('{bad')
    assert request(mod)[0] == 503
    assert request(mod, 'POST', {'id': 'external-app-tab', 'url': '', 'label': 'App'})[0] == 503
    assert (tmp_path / 'external-apps.json').read_text() == '{bad'
