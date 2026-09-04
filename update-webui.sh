#!/usr/bin/env bash
set -euo pipefail
LOG_DIR=/opt/hermes-webui
LOG_FILE="$LOG_DIR/update-webui.log"
exec >>"$LOG_FILE" 2>&1

echo "[$(date -Is)] starting Hermes WebUI update"
cd /opt/hermes-webui

branch=$(git rev-parse --abbrev-ref HEAD)
git fetch origin master --prune
remote_sha=$(git rev-parse origin/master)
local_sha=$(git rev-parse HEAD)
merge_base=$(git merge-base HEAD origin/master)

if [ "$local_sha" = "$remote_sha" ]; then
  echo "[$(date -Is)] already exactly at origin/master ($local_sha)"
  exit 0
fi

if [ "$merge_base" = "$remote_sha" ]; then
  echo "[$(date -Is)] branch $branch already contains origin/master ($remote_sha); nothing to update"
  exit 0
fi

echo "[$(date -Is)] rebasing $branch onto origin/master: $local_sha -> $remote_sha"
git rebase origin/master

if [ -x /opt/hermes-webui/.venv/bin/python ]; then
  # Run pip through the venv interpreter. Its pip launcher can retain a stale
  # shebang after a Python upgrade even when the active interpreter is healthy.
  /opt/hermes-webui/.venv/bin/python -m pip install -r /opt/hermes-webui/requirements.txt
fi

if systemctl list-unit-files hermes-webui.service >/dev/null 2>&1; then
  systemctl restart hermes-webui.service
else
  if [ -x /opt/hermes-webui/stop-local.sh ]; then
    /opt/hermes-webui/stop-local.sh || true
  fi
  sleep 2
  if [ -x /opt/hermes-webui/run-local.sh ]; then
    /opt/hermes-webui/run-local.sh
  else
    set -a
    . /opt/hermes-webui/.env
    set +a
    nohup /opt/hermes-webui/.venv/bin/python /opt/hermes-webui/server.py > /opt/hermes-webui/hermes-webui-host.log 2>&1 &
    echo $! > /opt/hermes-webui/hermes-webui.pid
  fi
fi

sleep 3
curl -fsS http://127.0.0.1/health >/dev/null

echo "[$(date -Is)] update complete"
