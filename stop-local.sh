#!/usr/bin/env bash
set -euo pipefail

if systemctl list-unit-files hermes-webui.service >/dev/null 2>&1; then
  systemctl stop hermes-webui.service
  exit 0
fi

if [[ -f /opt/hermes-webui/hermes-webui.pid ]]; then
  pid=$(cat /opt/hermes-webui/hermes-webui.pid || true)
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" || true
  fi
  rm -f /opt/hermes-webui/hermes-webui.pid
fi
