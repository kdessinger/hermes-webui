#!/usr/bin/env bash
# Combined weekly maintenance for Hermes harness + Hermes WebUI.
# Runs the WebUI update first (low risk, proven cron), then the Hermes
# harness update (which carries Kenn's local modifications and stashes/
# re-applies them via a safety branch + tar backup).
#
# Schedule: Sundays 08:15 UTC = ~04:15 America/New_York (DST aware).
# Replace the existing single WebUI cron entry with this wrapper.
set -uo pipefail

LOG_DIR=/opt/hermes-webui
LOG_FILE="$LOG_DIR/maintenance-weekly.log"
HERMES_AGENT_DIR=/root/.hermes/hermes-agent
HERMES_BIN=/root/.local/bin/hermes
SAFETY_BACKUP_DIR=/root/.hermes/backups/harness-preserve
SUMMARY_FILE="$LOG_DIR/maintenance-weekly-summary.json"

mkdir -p "$LOG_DIR" "$SAFETY_BACKUP_DIR"
exec >>"$LOG_FILE" 2>&1

started_at="$(date -Is)"
echo "[$started_at] === weekly maintenance started ==="

webui_rc=0
hermes_rc=0
webui_message="skipped"
hermes_message="skipped"
agent_head_before=""
agent_head_after=""
webui_restart_after_agent_update="skipped"

# ---------------------------------------------------------------------------
# 1) WebUI update
# ---------------------------------------------------------------------------
echo "[$(date -Is)] step 1: WebUI update"
if [ -x /opt/hermes-webui/update-webui.sh ]; then
  if /opt/hermes-webui/update-webui.sh; then
    webui_rc=0
    webui_message="ok"
  else
    webui_rc=$?
    webui_message="update-webui.sh failed exit=$webui_rc"
  fi
else
  webui_rc=127
  webui_message="update-webui.sh not found or not executable"
fi
echo "[$(date -Is)] WebUI step rc=$webui_rc msg=$webui_message"

# ---------------------------------------------------------------------------
# 2) Hermes harness update
#    a) tar the current tree (excluding venv + git objects)
#    b) commit any local modifications onto a dated safety branch
#    c) run `hermes update --yes` against main
#    d) verify gpt-5.4 compression pin and gateway health
# ---------------------------------------------------------------------------
echo "[$(date -Is)] step 2: Hermes harness update"

if [ -d "$HERMES_AGENT_DIR/.git" ]; then
  cd "$HERMES_AGENT_DIR" || { hermes_rc=2; hermes_message="cd failed"; }

  if [ $hermes_rc -eq 0 ]; then
    agent_head_before="$(git rev-parse --verify HEAD 2>/dev/null || true)"
    stamp="$(date -u +%Y%m%d)"
    # 2a) tar backup
    tarball="$SAFETY_BACKUP_DIR/hermes-agent-pre-weekly-$stamp.tar.gz"
    tar --exclude='.venv' --exclude='__pycache__' --exclude='node_modules' \
        --exclude='.git/objects' -czf "$tarball" \
        -C /root/.hermes hermes-agent
    echo "[$(date -Is)] backup: $tarball ($(du -h "$tarball" | cut -f1))"

    # 2b) commit local mods onto a dated safety branch if dirty
    if [ -n "$(git status --porcelain)" ]; then
      safety_branch="kenn/local-harness-preserve-$stamp"
      git checkout -b "$safety_branch" >/dev/null 2>&1 || true
      git add -A
      git -c user.email='hermes@local' -c user.name='Hermes' \
          commit -m "preserve local harness modifications (weekly $stamp)" \
          >/dev/null 2>&1 || true
      # Return to main so `hermes update` operates on a clean checkout
      git checkout main >/dev/null 2>&1 || git checkout master >/dev/null 2>&1 || true
      echo "[$(date -Is)] safety branch: $safety_branch"
    fi

    # 2c) update
    if "$HERMES_BIN" update --yes >/dev/null 2>&1; then
      hermes_rc=0
    else
      hermes_rc=$?
    fi

    # 2d) verify gpt-5.4 compression pin + gateway
    agent_head_after="$(git rev-parse --verify HEAD 2>/dev/null || true)"
    pin_ok="no"
    if grep -qE '^\s*model:\s*gpt-5\.4\s*$' /root/.hermes/config.yaml 2>/dev/null; then
      pin_ok="yes"
    fi
    version_line="$("$HERMES_BIN" --version 2>&1 | head -1)"
    gateway_state="$("$HERMES_BIN" gateway status 2>&1 | grep -oE 'active \(running\)|inactive' | head -1 || echo 'unknown')"

    hermes_message="rc=$hermes_rc version=$version_line pin=$pin_ok gateway=$gateway_state"

    if [ "$pin_ok" != "yes" ]; then
      echo "[$(date -Is)] WARNING: gpt-5.4 compression pin missing after update"
    fi
  fi
else
  hermes_rc=3
  hermes_message="hermes-agent dir missing or not a git repo"
fi
echo "[$(date -Is)] Hermes step $hermes_message"

# ---------------------------------------------------------------------------
# 3) Restart WebUI if the Hermes Agent checkout changed
#    WebUI imports run_agent.AIAgent into its long-lived process. If the Hermes
#    Agent revision changes after WebUI starts, WebUI correctly fail-closes chat
#    starts with `agent_runtime_stale` until the process is restarted.
# ---------------------------------------------------------------------------
if [ "$hermes_rc" -eq 0 ] && [ -n "$agent_head_before" ] && [ -n "$agent_head_after" ] && [ "$agent_head_before" != "$agent_head_after" ]; then
  echo "[$(date -Is)] Hermes Agent HEAD changed ($agent_head_before -> $agent_head_after); restarting WebUI"
  if systemctl restart hermes-webui.service && sleep 3 && curl -fsS http://127.0.0.1/health >/dev/null; then
    webui_restart_after_agent_update="ok"
  else
    webui_restart_after_agent_update="failed"
    echo "[$(date -Is)] WARNING: WebUI restart after Hermes Agent update failed"
  fi
else
  webui_restart_after_agent_update="not-needed"
fi

echo "[$(date -Is)] WebUI post-agent-update restart: $webui_restart_after_agent_update"

# ---------------------------------------------------------------------------
# 4) Skills + summary
# ---------------------------------------------------------------------------
echo "[$(date -Is)] step 4: skills update (best effort)"
"$HERMES_BIN" skills update >/dev/null 2>&1 || true

finished_at="$(date -Is)"
echo "[$finished_at] === weekly maintenance finished (webui=$webui_rc hermes=$hermes_rc) ==="

# Single-line summary suitable for cron mail or grep
printf '{"started":"%s","finished":"%s","webui":{"rc":%d,"msg":"%s","post_agent_restart":"%s"},"hermes":{"rc":%d,"msg":"%s","head_before":"%s","head_after":"%s"}}\n' \
  "$started_at" "$finished_at" "$webui_rc" "$webui_message" "$webui_restart_after_agent_update" \
  "$hermes_rc" "$hermes_message" "$agent_head_before" "$agent_head_after" > "$SUMMARY_FILE"

# Non-zero exit only if Hermes failed (WebUI failure is non-fatal)
exit $hermes_rc
