# Maintaining the OpenRouter speech customization

This feature is maintained on `kenn/webui-customizations`, on top of the upstream
Hermes WebUI code and the existing Cartesia integration. It is a local
customization, not a claim of upstream inclusion.

## Update rules

1. Keep the feature and tests committed. Keep credentials, `.env`, sessions,
   attachments, logs, runtime settings and databases outside Git.
2. Back up the customization branch to an approved private remote. A local
   branch or an archive on the same host is not an off-machine backup.
3. Before updating, inspect `git status`, branch ancestry and the current known-good
   commit. Preserve unrelated uncommitted work separately; do not stage or discard
   it as part of TTS maintenance.
4. Fetch the intended upstream release without changing the live checkout. Create
   an isolated candidate worktree/branch, merge or replay the customization there,
   and stop on conflicts. Never fix an update by resetting the customization branch
   to upstream, overwriting complete files, or auto-resolving conflicts.
5. Run the catalog, synthesis, preview, preference, playback and security tests via
   `scripts/test.sh` with isolated state. Also run
   `node tests/openrouter_voice_preview.cjs` and JavaScript syntax checks.
6. In the candidate, verify model discovery, current-model voice requests,
   persisted selections, preview loading/stop/error feedback, manual Listen,
   automatic read-aloud and voice-mode routing. Use an explicitly approved small
   live synthesis to distinguish mocked coverage from real provider availability.
7. Deploy only after tests pass, with a known-good rollback commit and a backup of
   configuration/state. Coordinate all running chats before restarting WebUI;
   a chat agent can itself be running inside the service being restarted.
8. Verify health, served HTML/JS asset versions, and browser audio. Bump static asset
   cache keys when controls/handlers change. Preserve selected TTS preferences.

A stock fast-forward updater may reject this diverged customization branch.
An existing local rebase updater may stop on a dirty tree or conflicting upstream
changes. Treat that as a safety stop, not an invitation to force the update.
Committing the feature makes it recoverable; it does not guarantee future merges
will be conflict-free. Updating the updater or scheduler is a separate change.

## Porting and recovery

Read `docs/openrouter-tts.md` for the user workflow and runtime contract. The feature
uses dedicated `api/openrouter_tts.py` and `static/openrouter-tts.js` modules plus
integration changes in routes, settings, page markup and the existing playback
paths. A single-file copy is not sufficient.

Prefer cloning the backed-up branch when restoring an equivalent deployment.
For a different WebUI revision, apply a reviewed feature patch or adapt the source
against that revision, preserving its authentication and lifecycle contracts.
Never copy personal runtime data or credentials as part of a feature handoff.

Known remaining limitation: the preview button is functional, but its primary
button classes did not render as the expected yellow pill in the user's theme.
Human-verified playback is stronger evidence than the styling class assertion.
