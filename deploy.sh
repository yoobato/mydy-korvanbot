#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
action="${1:-prepare}"
case "$action" in prepare|start) ;; *) echo 'Usage: bash deploy.sh [prepare|start]' >&2; exit 1;; esac
if [[ "$(git branch --show-current)" != main ]] || [[ -n "$(git status --porcelain)" ]]; then
  echo 'Commit changes on main before deploying.' >&2
  exit 1
fi
git fetch origin main
if [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
  echo 'Push main before deploying.' >&2
  exit 1
fi
ssh yoobato-canada-lightsail 'sudo install -d -o ubuntu -g ubuntu /opt/services/korvanbot; sudo install -d -m 700 -o ubuntu -g ubuntu /opt/secrets/korvanbot'
git archive HEAD | ssh yoobato-canada-lightsail 'tar -xf - -C /opt/services/korvanbot'
git rev-parse HEAD | ssh yoobato-canada-lightsail 'cat > /opt/services/korvanbot/DEPLOYED_REVISION'
ssh yoobato-canada-lightsail 'cd /opt/services/korvanbot; KORVANBOT_ENV_FILE=/opt/secrets/korvanbot/telegram.env docker compose build'
if [[ "$action" == start ]]; then
  # Empty/missing secrets must not put the service into a restart loop.
  ssh yoobato-canada-lightsail 'python3 - <<'"'"'PY'"'"'
from pathlib import Path
p = Path("/opt/secrets/korvanbot/telegram.env")
values = dict(line.split("=", 1) for line in p.read_text().splitlines() if "=" in line and not line.startswith("#"))
if not all(values.get(key, "").strip() for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID")):
    raise SystemExit("Configure server Telegram credentials before starting")
PY'
  ssh yoobato-canada-lightsail 'cd /opt/services/korvanbot; KORVANBOT_ENV_FILE=/opt/secrets/korvanbot/telegram.env docker compose up -d'
fi
