#!/usr/bin/env bash
set -euo pipefail

if systemctl list-unit-files hermes-webui.service >/dev/null 2>&1; then
  systemctl restart hermes-webui.service
  systemctl --no-pager --lines=20 status hermes-webui.service
  exit 0
fi

cd /opt/hermes-webui
if [[ -f hermes-webui.pid ]]; then
  pid=$(cat hermes-webui.pid || true)
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" || true
    sleep 1
  fi
fi
set -a
source /opt/hermes-webui/.env
set +a
nohup /opt/hermes-webui/.venv/bin/python /opt/hermes-webui/server.py >> /opt/hermes-webui/hermes-webui-host.log 2>&1 &
echo $! > /opt/hermes-webui/hermes-webui.pid
echo "started pid $(cat /opt/hermes-webui/hermes-webui.pid)"
