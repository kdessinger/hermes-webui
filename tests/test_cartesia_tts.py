"""Regression coverage for the native Cartesia server-side TTS engine."""

import io
import json
from pathlib import Path

import pytest

import api.routes as routes


class _FakeHandler:
    def __init__(self, body: dict, *, client="10.72.0.1"):
        encoded = json.dumps(body).encode("utf-8")
        self.command = "POST"
        self.rfile = io.BytesIO(encoded)
        self.wfile = io.BytesIO()
        self.headers = {"Content-Length": str(len(encoded))}
        self.client_address = (client, 12345)
        self.status = None
        self.sent_headers = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.sent_headers[key] = value

    def end_headers(self):
        pass

    def payload(self):
        try:
            return json.loads(self.wfile.getvalue().decode("utf-8"))
        except Exception:
            return None


class _AudioResponse:
    headers = {"Content-Type": "audio/mpeg"}

    def __init__(self, audio=b"ID3cartesia-audio"):
        self._audio = audio

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _size=-1):
        audio, self._audio = self._audio, b""
        return audio


@pytest.fixture(autouse=True)
def _isolated_tts(monkeypatch):
    import api.auth as auth

    monkeypatch.setattr(auth, "is_auth_enabled", lambda: False)
    monkeypatch.setattr(routes, "is_auth_enabled", lambda: False, raising=False)
    monkeypatch.delenv("HERMES_WEBUI_TRUST_FORWARDED_FOR", raising=False)
    monkeypatch.delenv("CARTESIA_API_KEY", raising=False)
    if hasattr(routes._handle_tts, "_tts_limiter"):
        del routes._handle_tts._tts_limiter
    yield
    if hasattr(routes._handle_tts, "_tts_limiter"):
        del routes._handle_tts._tts_limiter


def test_cartesia_missing_key_returns_503_without_network(monkeypatch):
    import api.onboarding as onboarding

    monkeypatch.setattr(onboarding, "_load_env_file", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        routes,
        "_tts_open",
        lambda *_args, **_kwargs: pytest.fail("Cartesia upstream should not be called"),
    )

    handler = _FakeHandler({"text": "Hello", "engine": "cartesia"})
    routes._handle_tts(handler, None)

    assert handler.status == 503
    assert "CARTESIA_API_KEY" in (handler.payload() or {}).get("error", "")


def test_cartesia_sends_current_bytes_request_and_returns_mp3(monkeypatch):
    import api.config as config

    captured = {}
    monkeypatch.setenv("CARTESIA_API_KEY", "cartesia-test-key")
    monkeypatch.setattr(config, "get_config", lambda: {
        "tts": {
            "cartesia": {
                "voice_id": "11111111-2222-3333-4444-555555555555",
                "model": "sonic-3",
                "sample_rate": 24000,
                "bit_rate": 96000,
            }
        }
    })

    def _fake_tts_open(req, *, timeout, opener_factory):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        captured["opener_factory"] = opener_factory
        return _AudioResponse()

    monkeypatch.setattr(routes, "_tts_open", _fake_tts_open)
    handler = _FakeHandler({
        "text": "Hello from Cartesia",
        "voice": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "engine": "cartesia",
    })
    routes._handle_tts(handler, None)

    assert handler.status == 200
    assert handler.sent_headers["Content-Type"] == "audio/mpeg"
    assert handler.wfile.getvalue() == b"ID3cartesia-audio"
    assert captured["url"] == "https://api.cartesia.ai/tts/bytes"
    assert captured["timeout"] == 30
    assert captured["headers"]["Authorization"] == "Bearer cartesia-test-key"
    assert captured["headers"]["Cartesia-version"] == "2026-03-01"
    assert captured["body"] == {
        "model_id": "sonic-3",
        "transcript": "Hello from Cartesia",
        "voice": {"mode": "id", "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"},
        "output_format": {
            "container": "mp3",
            "sample_rate": 24000,
            "bit_rate": 96000,
        },
    }


def test_cartesia_rejects_invalid_config_voice_before_network(monkeypatch):
    import api.config as config

    monkeypatch.setenv("CARTESIA_API_KEY", "cartesia-test-key")
    monkeypatch.setattr(config, "get_config", lambda: {
        "tts": {"cartesia": {"voice_id": "not-a-cartesia-voice"}}
    })
    monkeypatch.setattr(
        routes,
        "_tts_open",
        lambda *_args, **_kwargs: pytest.fail("Cartesia upstream should not be called"),
    )

    handler = _FakeHandler({"text": "Hello", "engine": "cartesia"})
    routes._handle_tts(handler, None)

    assert handler.status == 400
    assert "voice_id" in (handler.payload() or {}).get("error", "")


def test_persisted_cartesia_engine_is_used_when_request_omits_engine(monkeypatch):
    import api.config as config

    monkeypatch.setenv("CARTESIA_API_KEY", "cartesia-test-key")
    monkeypatch.setattr(routes, "load_settings", lambda: {"tts_engine": "cartesia"})
    monkeypatch.setattr(config, "get_config", lambda: {"tts": {"cartesia": {}}})
    monkeypatch.setattr(routes, "_tts_open", lambda *_args, **_kwargs: _AudioResponse(b"persisted-cartesia"))

    handler = _FakeHandler({"text": "Hello"})
    routes._handle_tts(handler, None)

    assert handler.status == 200
    assert handler.wfile.getvalue() == b"persisted-cartesia"


def test_cartesia_is_wired_through_settings_and_both_playback_paths():
    root = Path(__file__).resolve().parent.parent
    index_html = (root / "static" / "index.html").read_text(encoding="utf-8")
    panels_js = (root / "static" / "panels.js").read_text(encoding="utf-8")
    ui_js = (root / "static" / "ui.js").read_text(encoding="utf-8")

    assert '<option value="cartesia">Cartesia (server)</option>' in index_html
    assert 'id="settingsCartesiaVoiceId"' in index_html
    assert "engine==='cartesia'" in panels_js
    assert "function _playCartesiaTts(text, btn)" in ui_js
    assert "engine:'cartesia'" in ui_js
    assert "_playCartesiaTts(clean, btn);" in ui_js
    assert "_playCartesiaTts(clean, null);" in ui_js
