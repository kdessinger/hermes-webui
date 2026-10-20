"""OpenRouter speech uses the existing authenticated server TTS contract."""
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest
import api.routes as routes
from tests.test_cartesia_tts import _FakeHandler, _AudioResponse


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    import api.auth as auth
    import api.config as config
    import api.onboarding as onboarding
    monkeypatch.setattr(auth, 'is_auth_enabled', lambda: False)
    monkeypatch.setattr(config, 'get_config', lambda: {})
    monkeypatch.setattr(onboarding, '_load_env_file', lambda *_a, **_kw: {})
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    monkeypatch.setattr(routes, 'load_settings', lambda: {})
    if hasattr(routes._handle_tts, '_tts_limiter'):
        del routes._handle_tts._tts_limiter
    yield
    if hasattr(routes._handle_tts, '_tts_limiter'):
        del routes._handle_tts._tts_limiter


def test_missing_key(monkeypatch):
    monkeypatch.setattr(routes, '_tts_open', lambda *a, **kw: pytest.fail('no network'))
    h = _FakeHandler({'text': 'Hello', 'engine': 'openrouter'})
    routes._handle_tts(h, None)
    assert h.status == 503
    assert 'OPENROUTER_API_KEY' in h.payload()['error']


@pytest.mark.parametrize('voice', ['', 'bram', 'nadine', 'vincent'])
def test_request_returns_mp3(monkeypatch, voice):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only-key')
    def upstream(req, *, timeout, opener_factory):
        assert req.full_url == 'https://openrouter.ai/api/v1/audio/speech'
        assert req.get_header('Authorization') == 'Bearer test-only-key'
        assert timeout == 30
        assert json.loads(req.data) == {
            'model': 'heygen/heygen-voice-1-turbo', 'input': 'Hello',
            'voice': voice or 'nadine', 'response_format': 'mp3',
        }
        return _AudioResponse(b'ID3openrouter')
    monkeypatch.setattr(routes, '_tts_open', upstream)
    h = _FakeHandler({'text': 'Hello', 'engine': 'openrouter', 'voice': voice})
    routes._handle_tts(h, None)
    assert h.status == 200
    assert h.sent_headers['Content-Type'] == 'audio/mpeg'
    assert h.sent_headers['Cache-Control'] == 'no-store'
    assert h.wfile.getvalue() == b'ID3openrouter'


def test_profile_key_and_persisted_engine(monkeypatch):
    import api.onboarding as onboarding
    monkeypatch.setattr(onboarding, '_load_env_file', lambda *_a: {'OPENROUTER_API_KEY': 'profile-key'})
    monkeypatch.setattr(routes, 'load_settings', lambda: {'tts_engine': 'openrouter'})
    monkeypatch.setattr(routes, '_tts_open', lambda *a, **kw: _AudioResponse())
    h = _FakeHandler({'text': 'Hello'})
    routes._handle_tts(h, None)
    assert h.status == 200


@pytest.mark.parametrize('voice', ['unknown', 'en-US-GuyNeural', '../bram'])
def test_invalid_explicit_voice(monkeypatch, voice):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only-key')
    monkeypatch.setattr(routes, '_tts_open', lambda *a, **kw: pytest.fail('no network'))
    h = _FakeHandler({'text': 'Hello', 'engine': 'openrouter', 'voice': voice})
    routes._handle_tts(h, None)
    assert h.status == 400


@pytest.mark.parametrize('failure', ['non-audio', 'empty', 'upstream'])
def test_upstream_failures(monkeypatch, failure):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only-key')
    def upstream(*a, **kw):
        if failure == 'upstream':
            raise HTTPError('https://openrouter.ai/api/v1/audio/speech', 402, 'credits', {}, io.BytesIO(b'secret upstream detail'))
        r = _AudioResponse(b'' if failure == 'empty' else b'{"error":"failed"}')
        if failure == 'non-audio':
            r.headers = {'Content-Type': 'application/json'}
        return r
    monkeypatch.setattr(routes, '_tts_open', upstream)
    h = _FakeHandler({'text': 'Hello', 'engine': 'openrouter'})
    routes._handle_tts(h, None)
    assert h.status == 502
    assert 'secret upstream detail' not in h.wfile.getvalue().decode()


def test_ui_paths():
    root = Path(__file__).resolve().parent.parent / 'static'
    html = (root / 'index.html').read_text()
    panels = (root / 'panels.js').read_text()
    ui = (root / 'ui.js').read_text()
    assert '<option value="openrouter">OpenRouter (server)</option>' in html
    assert "engine==='openrouter'" in panels
    assert "'nadine','tabitha','bram','gareth','noelle','meredith','sabrina','lucian','weston','vincent'" in panels
    assert '_playOpenRouterTts(clean, btn);' in ui
    assert '_playOpenRouterTts(clean, null);' in ui
    assert "engine:'openrouter'" in ui
