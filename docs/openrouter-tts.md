# OpenRouter speech in WebUI

In **Settings → Preferences**, choose **OpenRouter (server)** as the TTS engine.
The OpenRouter speech section provides a model selector, a **Refresh speech
catalog** button, and voices for the selected model. Models without a published
voice list expose an optional provider voice-ID input instead.

Use **▶ Preview** beside **Model voice** to hear a short sample of the current
model and voice. It becomes **■ Stop** while generating or playing. Previews
use OpenRouter credits and do not change the selected engine, automatic
read-aloud, or persisted preferences. Switching the model or voice stops the
current preview. Stopping an in-flight request does not guarantee the upstream
provider cancels generation or its charge. Errors appear below the button.

The key is `OPENROUTER_API_KEY`, read on the server from the environment or the
active Hermes profile's `.env`. It is never sent to the browser. Selecting a
provider does not require a separate account with that upstream provider unless
OpenRouter specifically requires BYOK for the requested capability.

## Discovery and persistence

- Catalog source: `GET https://openrouter.ai/api/v1/models?output_modalities=speech`.
  The unfiltered model catalog can omit speech models. Only the `speech` output
  modality is admitted; conversational audio models are not treated as TTS.
- Names and `supported_voices` come from the catalog, preserving exact case.
- Catalog requests are cached for one hour with a 30-second refresh cooldown.
  On failure the last cache, or a bundled public snapshot, remains available;
  the API marks expired/snapshot data stale. Listing is not proof that a model
  has an available provider or that an account can use it.
- `tts_openrouter_model` and `tts_openrouter_voice` are persisted speech settings.
  Per-model voice history is browser-local. Changing models resets/restores that
  model's voice rather than forwarding another provider's voice ID. Refreshing
  preserves the selected model, even if it has disappeared from the catalog.
- Existing generic HeyGen voice preferences migrate in the browser. Other TTS
  engines and the currently selected engine are not changed by installation.

## Synthesis and boundaries

The server sends the exact selected model to `/api/v1/audio/speech`. Most models
use MP3. Gemini TTS requires PCM despite OpenRouter model docs advertising MP3;
Gemini PCM is wrapped server-side as WAV using its sample-rate/channel metadata
(24 kHz mono by default). No extra generation retry is needed. The provider chooses its default
voice when none is supplied (HeyGen retains its original Nadine default).
Unknown models and invalid listed voices are rejected before synthesis; refresh
the catalog when a new model is released. Custom voice IDs are allowed only for
models without a published voice list.

Listen, automatic read-aloud, and voice-mode speech use the same model/voice
selection. API credentials stay server-side. The existing TTS authentication,
rate limiter, public-IP pinning, redirect rejection, response-size cap, and
non-audio-response rejection remain in force; empty audio is also rejected.
There is no automatic model retry or paid fallback. Free models may have quotas
or no available provider; upstream failures are not evidence of a local setup
failure. A successful catalog refresh does not test synthesis or listening quality
for every model.

## Verification

Run `./scripts/test.sh` with isolated test state per `AGENTS.md`. Relevant tests:
`test_openrouter_catalog.py`, `test_openrouter_tts.py`, `test_cartesia_tts.py`, and
neighboring speech preference/playback/security tests. Catalog tests include
real loopback HTTP settings persistence and isolate/restore their settings state.
Provider request tests mock upstream network; they do not establish upstream
availability. Browser checks should cover model-specific voice lists, custom
voice IDs, switching away and back, refresh preservation, and narrow layouts.
