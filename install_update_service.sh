#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(id -un)"
if [[ "$USER_NAME" == root ]]; then echo "Run as your normal Ubuntu login (not sudo)."; exit 1; fi
command -v docker >/dev/null || { echo 'Docker is required'; exit 1; }
command -v systemctl >/dev/null || { echo 'systemd is required'; exit 1; }
[[ -f "$ROOT/update_worker.py" && -f "$ROOT/apply_update.py" ]] || { echo 'Missing updater files. Copy the bootstrap files into ~/jarvis first.'; exit 1; }
cd "$ROOT"
docker compose ps >/dev/null || { echo "Your user cannot access Docker Compose. Fix Docker group permissions first."; exit 1; }
mkdir -p "$ROOT/data/updates" "$ROOT/data/update_backups"
# Only adjust the updater's dedicated directories, never the database or printer config.
sudo chown "$USER_NAME:$USER_NAME" "$ROOT/data/updates" "$ROOT/data/update_backups"
sudo chmod 750 "$ROOT/data/updates" "$ROOT/data/update_backups"
SERVICE=/etc/systemd/system/jarvis-updater.service
sudo tee "$SERVICE" >/dev/null <<EOF
[Unit]
Description=JARVIS local update worker
After=docker.service
Requires=docker.service
[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$ROOT
ExecStart=/usr/bin/python3 $ROOT/update_worker.py
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=full
ReadWritePaths=$ROOT
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now jarvis-updater.service
sudo systemctl restart jarvis-updater.service
sudo systemctl status jarvis-updater.service --no-pager
printf '\nUpdater installed. Future JARVIS project ZIPs can be uploaded and applied in System Updates.\n'
