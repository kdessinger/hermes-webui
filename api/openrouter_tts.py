"""Public, bounded OpenRouter speech discovery; credentials never enter the catalog.

The speech filter is essential: the unfiltered model catalog omits these models.
A bundled public snapshot is an explicitly stale fallback, not live availability.
"""
import json
from pathlib import Path
import re
import threading
import time
from urllib.request import Request, build_opener, ProxyHandler

DEFAULT_MODEL = 'heygen/heygen-voice-1-turbo'
MODEL_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:-]{0,180}\Z')
_lock = threading.Lock()
_cache = None
_last_attempt = 0


def normalize_catalog(payload):
    models = {}
    for row in payload.get('data', []):
        if not isinstance(row, dict):
            continue
        model = row.get('id')
        if not isinstance(model, str) or not MODEL_RE.fullmatch(model):
            continue
        if 'speech' not in (row.get('architecture') or {}).get('output_modalities', []):
            continue
        if model in models:
            continue
        voices = row.get('supported_voices') or []
        voices = list(dict.fromkeys(v for v in voices if isinstance(v, str) and 0 < len(v) <= 200 and not any(ord(c) < 32 for c in v)))
        models[model] = {'id': model, 'name': str(row.get('name') or model)[:200], 'voices': voices}
    return sorted(models.values(), key=lambda row: row['id'])


def _seed_catalog():
    return json.loads(Path(__file__).with_name('openrouter_tts_seed.json').read_text())


def _fetch_catalog():
    # Reuse the speech proxy's no-redirect and public-IP-pinned transport.
    from api.routes import _tts_open, _NoRedirectTtsHandler, _PinnedHTTPSHandler
    req = Request('https://openrouter.ai/api/v1/models?output_modalities=speech', headers={'Accept': 'application/json', 'User-Agent': 'Hermes-WebUI-TTS/1.0'})
    with _tts_open(req, timeout=15, opener_factory=lambda: build_opener(ProxyHandler({}), _NoRedirectTtsHandler(), _PinnedHTTPSHandler())) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('catalog too large')
    models = normalize_catalog(json.loads(raw))
    if not models:
        raise ValueError('empty speech catalog')
    return models


def get_catalog(*, refresh=False):
    global _cache, _last_attempt
    with _lock:
        now = time.time()
        if _cache and not refresh and now - _cache['fetched_at'] < 3600:
            return dict(_cache, stale=False, source='live')
        # Collapse concurrent refreshes and bound repeated failures.
        if now - _last_attempt >= 30:
            _last_attempt = now
            try:
                _cache = {'models': _fetch_catalog(), 'fetched_at': time.time()}
                return dict(_cache, stale=False, source='live')
            except Exception:
                pass
        if _cache:
            stale = now - _cache['fetched_at'] >= 3600
            return dict(_cache, stale=stale, source='cache')
        return {'models': _seed_catalog(), 'fetched_at': None, 'stale': True, 'source': 'bundled snapshot'}


def speech_payload(text, model, voice):
    if not isinstance(model, str) or not MODEL_RE.fullmatch(model):
        raise ValueError('invalid OpenRouter model ID')
    catalog = get_catalog()
    metadata = next((row for row in catalog['models'] if row['id'] == model), None)
    if metadata is None:
        raise ValueError('model is not in the speech catalog; refresh the catalog')
    if not isinstance(voice, str) or len(voice) > 200 or any(ord(c) < 32 for c in voice):
        raise ValueError('invalid OpenRouter voice')
    if voice and metadata['voices'] and voice not in metadata['voices']:
        raise ValueError('voice is not supported by the selected OpenRouter model')
    result = {'model': model, 'input': text, 'response_format': 'mp3'}
    # Preserve the original HeyGen default; other providers choose their own.
    if not voice and model.startswith('heygen/'):
        voice = 'nadine'
    if voice:
        result['voice'] = voice
    return result
