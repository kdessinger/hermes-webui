"""Dynamic speech discovery must exclude conversational audio and preserve selection."""
import pytest


def test_catalog_filters_deduplicates_and_preserves_voice_case():
    from api.openrouter_tts import normalize_catalog
    rows = normalize_catalog({'data': [
        {'id': 'google/test', 'name': 'Google test', 'architecture': {'output_modalities': ['speech']}, 'supported_voices': ['Kore', 'Kore', 'Puck']},
        {'id': 'openai/chat', 'architecture': {'output_modalities': ['audio', 'text']}},
        {'id': 'google/test', 'architecture': {'output_modalities': ['speech']}},
        {'id': '../bad', 'architecture': {'output_modalities': ['speech']}},
        {'id': 'fish/custom:free', 'architecture': {'output_modalities': ['speech']}},
    ]})
    assert len(rows) == 2
    assert rows[1]['voices'] == ['Kore', 'Puck']
    assert rows[0]['voices'] == []


def test_dynamic_request_and_no_voice_for_provider_default(monkeypatch):
    import api.openrouter_tts as tts
    monkeypatch.setattr(tts, 'get_catalog', lambda **kw: {'models': [
        {'id': 'fish-audio/new:free', 'voices': []},
        {'id': 'google/new', 'voices': ['Kore']},
    ]})
    assert tts.speech_payload('Hi', 'fish-audio/new:free', '') == {
        'model': 'fish-audio/new:free', 'input': 'Hi', 'response_format': 'mp3'}
    assert tts.speech_payload('Hi', 'google/new', 'Kore')['voice'] == 'Kore'
    with pytest.raises(ValueError):
        tts.speech_payload('Hi', 'google/new', 'nadine')
    with pytest.raises(ValueError):
        tts.speech_payload('Hi', 'missing/model', '')
    with pytest.raises(ValueError):
        tts.speech_payload('Hi', 'fish-audio/new:free', '\nsecret')


def test_refresh_failure_uses_stale_cache(monkeypatch):
    import api.openrouter_tts as tts
    monkeypatch.setattr(tts, '_cache', {'models': [{'id': 'kept/model', 'voices': []}], 'fetched_at': 1})
    monkeypatch.setattr(tts, '_last_attempt', 0)
    def fail(): raise OSError('offline')
    monkeypatch.setattr(tts, '_fetch_catalog', fail)
    result = tts.get_catalog(refresh=True)
    assert result['stale'] is True
    assert result['models'][0]['id'] == 'kept/model'


def test_seed_has_all_requested_models():
    import api.openrouter_tts as tts
    rows = tts._seed_catalog()
    ids = {m['id'] for m in rows}
    assert {'heygen/heygen-voice-1', 'heygen/heygen-voice-1-turbo', 'fish-audio/drama-3', 'fish-audio/s2-pro', 'fish-audio/s2.1-pro', 'fish-audio/s2.1-pro-free:free', 'google/gemini-3.8-flash-lite-tts', 'google/gemini-3.8-flash-tts', 'x-ai/grok-voice-tts-1.0', 'sesame/csm-1b', 'canopylabs/orpheus-3b-0.1-ft', 'hexgrad/kokoro-82m'} <= ids
    assert len(ids) == len(rows)


def test_catalog_http_and_settings_roundtrip():
    import json
    from urllib.request import urlopen, Request
    from tests._pytest_port import BASE
    with urlopen(BASE + '/api/tts/openrouter/models', timeout=30) as resp:
        result = json.load(resp)
    assert len(result['models']) >= 12
    assert all('voices' in row for row in result['models'])
    with urlopen(BASE + '/api/settings', timeout=10) as resp:
        before = json.load(resp)
    import os
    from pathlib import Path
    settings_file = Path(os.environ['HERMES_WEBUI_TEST_STATE_DIR']) / 'settings.json'
    original = settings_file.read_bytes() if settings_file.exists() else None
    payload = {'tts_openrouter_model': 'hexgrad/kokoro-82m', 'tts_openrouter_voice': 'am_onyx'}
    req = Request(BASE + '/api/settings', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=10) as resp:
            assert resp.status == 200
        with urlopen(BASE + '/api/settings', timeout=10) as resp:
            after = json.load(resp)
        assert all(after[k] == v for k, v in payload.items())
        assert after['tts_engine'] == before['tts_engine']
        assert set(payload) <= set(after['persisted_speech_keys'])
    finally:
        # Do not leak persisted keys into neighboring shared-server tests.
        if original is None:
            settings_file.unlink(missing_ok=True)
        else:
            settings_file.write_bytes(original)
