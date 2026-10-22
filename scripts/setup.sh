#!/usr/bin/env bash
# Jarvis setup for Ubuntu 24.04 (PipeWire + WirePlumber 0.4). Run from the repo root.
# Steps that need sudo are printed for you to run; everything else is done here.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1. Python environment"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "== 2. adb (Android platform-tools, user install)"
if ! command -v adb >/dev/null; then
  mkdir -p ~/.local/opt ~/.local/bin
  tmp=$(mktemp -d)
  curl -fsSLo "$tmp/pt.zip" https://dl.google.com/android/repository/platform-tools-latest-linux.zip
  unzip -qo "$tmp/pt.zip" -d ~/.local/opt/ && rm -rf "$tmp"
  ln -sf ~/.local/opt/platform-tools/adb ~/.local/bin/adb
fi
adb version | head -1

echo "== 3. WirePlumber: native HFP hands-free backend"
wp=$(wireplumber --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 || echo 0.4)
if [[ "$wp" == 0.4 ]]; then
  mkdir -p ~/.config/wireplumber/bluetooth.lua.d
  cp config/wireplumber/51-jarvis.lua ~/.config/wireplumber/bluetooth.lua.d/
else
  mkdir -p ~/.config/wireplumber/wireplumber.conf.d
  cp config/wireplumber/51-jarvis.conf ~/.config/wireplumber/wireplumber.conf.d/
fi
systemctl --user restart wireplumber

echo "== 4. Settings"
[[ -f .env ]] || { cp .env.example .env; echo "Created .env: edit it before running Jarvis"; }
if ! grep -qE '^JARVIS_ALERT_TOKEN=.{16,}' .env; then
  token=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
  sed -i '/^JARVIS_ALERT_TOKEN=/d' .env && echo "JARVIS_ALERT_TOKEN=$token" >> .env
  echo "Generated JARVIS_ALERT_TOKEN in .env (for /alerta and the MCP server)"
fi

cat <<'MSG'

== Run these yourself (sudo):

  # oFono must not run: it grabs the HFP profile and the call audio never reaches PipeWire
  sudo systemctl disable --now ofono 2>/dev/null || true

  # adb over USB for Samsung phones (other brands: change idVendor in the file)
  sudo cp config/udev/51-android.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger

Then follow README.md from "Emparejar el teléfono".
MSG
