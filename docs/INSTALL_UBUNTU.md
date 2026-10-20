# Install JARVIS ONE v1 on Ubuntu

Use Ubuntu/Linux with Docker Engine, Docker Compose plugin, Python 3, and internet access. These directions assume a **fresh** installation; for an existing install, read [UPGRADE.md](UPGRADE.md) instead.

## 1. Check requirements

```bash
python3 --version
docker --version
docker compose version
docker info >/dev/null && echo 'Docker access OK'
```

If Docker or Compose is missing, use the [official Docker Engine installation instructions for Ubuntu](https://docs.docker.com/engine/install/ubuntu/). You may need to re-login after adding your user to the `docker` group. Docker access is root-equivalent; do not grant it to untrusted accounts.

## 2. Download source

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/jarvis-one-ai-command-center.git
cd jarvis-one-ai-command-center
```

Alternatively download a GitHub source archive, extract it into a clean directory, and `cd` there. Do **not** extract on top of an existing JARVIS installation without first backing it up.

## 3. First-run setup

```bash
python3 setup.py
```

This generates a **unique admin password** and prints it **once**. Save it in a password manager. It also creates `config/printers.json`. Credentials go in `.env`, excluded from Git. Setup will not replace an existing `.env` or database.

To enable cloud AI chat, set `OPENROUTER_API_KEY=` or `NVIDIA_API_KEY=` in your local `.env`, choose the matching provider, and restart the JARVIS service after changes. OpenRouter/NVIDIA may have their own account policies and costs.

## 4. Build and start

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=80 jarvis
```

Docker downloads images for Python, Playwright/Chromium, Piper/Whisper dependencies. The first build and speech model download can take time and disk space. If Docker DNS fails, fix the host/Docker network first; don't delete the data volume.

## 5. Sign in

Browse to `http://SERVER_LAN_IP:8765` from your **trusted LAN**, using the username and generated password. The default web server uses HTTP Basic authentication; plain HTTP is not suitable for exposure to the internet or untrusted networks.

## 6. Optional configuration

- **Weather:** Appearance → Weather settings → latitude/longitude → Save. No `.env` edit needed.
- **Time zone:** Appearance → Time zone → choose region or Automatic.
- **Voice:** AI Chat → Enable “Hey JARVIS”, allow microphone permission. HTTPS is generally required for microphone use from a different device; browser restrictions apply.
- **Printers:** Edit `config/printers.json`, set printer access code environment entries locally, and restart JARVIS. The printer monitor is read-only.
- **Model choice:** Admin approves models, users select from approved options.

## 7. Keep it running and back it up

The Compose services use `restart: unless-stopped`. Back up `.env`, `data/` and private `config/` regularly; these include secrets and passwords. Keep backups off the public web and out of Git.

```bash
# Run from the repository directory; backs up only items that exist.
items=()
for path in .env data config; do [ ! -e "$path" ] || items+=("$path"); done
tar -czf "$HOME/jarvis-private-backup-$(date +%Y%m%d-%H%M).tar.gz" "${items[@]}"
```

Note: for a SQLite database being actively modified, consider briefly stopping JARVIS before the backup or taking a consistent SQLite backup; avoid copying a changing DB during writes.

## Optional: enable web-based ZIP updates

If you want the dashboard's **System Updates** panel to apply ZIP releases from the Ubuntu host, review the script and run:

```bash
bash install_update_service.sh
```

It installs a **systemd worker** via `sudo`, so only do this on a machine you administer. Code update ZIPs can execute new Python code; upload releases only from trusted sources.
