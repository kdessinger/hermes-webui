"""Gemini speech rejects MP3: wrap its signed PCM in browser-playable WAV."""
import io
import json
import wave
import pytest
import api.openrouter_tts as tts
import api.routes as routes
from tests.test_cartesia_tts import _FakeHandler, _AudioResponse


def test_gemini_requests_pcm(monkeypatch):
    monkeypatch.setattr(tts, 'get_catalog', lambda: {'models': [{'id':'google/gemini-3.8-flash-lite-tts','voices':['Sadachbia']}]})
    assert tts.speech_payload('Hello','google/gemini-3.8-flash-lite-tts','Sadachbia')['response_format']=='pcm'


def test_gemini_route_wraps_pcm(monkeypatch):
    import api.auth as auth
    monkeypatch.setattr(auth,'is_auth_enabled',lambda:False)
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-test-key')
    monkeypatch.setattr(routes,'load_settings',lambda:{})
    monkeypatch.setattr(tts,'get_catalog',lambda:{'models':[{'id':'google/gemini-3.8-flash-lite-tts','voices':['Sadachbia']}]})
    if hasattr(routes._handle_tts,'_tts_limiter'):delattr(routes._handle_tts,'_tts_limiter')
    pcm=b'\x01\x00\xff\xff'*240
    def upstream(req,**kw):
        assert json.loads(req.data)['response_format']=='pcm'
        response=_AudioResponse(pcm)
        response.headers={'Content-Type':'audio/pcm;rate=24000;channels=1'}
        return response
    monkeypatch.setattr(routes,'_tts_open',upstream)
    handler=_FakeHandler({'engine':'openrouter','model':'google/gemini-3.8-flash-lite-tts','voice':'Sadachbia','text':'Hello'})
    routes._handle_tts(handler,None)
    assert handler.status==200
    assert handler.sent_headers['Content-Type']=='audio/wav'
    with wave.open(io.BytesIO(handler.wfile.getvalue())) as wav:
        assert (wav.getframerate(),wav.getnchannels(),wav.getsampwidth())==(24000,1,2)
        assert wav.readframes(wav.getnframes())==pcm


@pytest.mark.parametrize('audio,content_type',[(b'\x00','audio/pcm;rate=24000;channels=1'),(b'\x00\x00','audio/pcm;rate=0;channels=1'),(b'{}','application/json')])
def test_pcm_rejects_invalid_data(audio,content_type):
    with pytest.raises(ValueError):tts.playable_audio(audio,content_type,pcm=True)
