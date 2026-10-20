# Upgrade existing JARVIS without losing settings

**Use the separate release asset** `JARVIS_v1_FULL_UPDATE.zip`, not the GitHub source ZIP. The updater reads code files from a validated ZIP and rebuilds Docker services while keeping your private `.env`, `data/`, saved voices and real printer configuration.

## Recommended: dashboard updater

1. Back up your installation, especially `.env`, `data/`, and `config/`.
2. Log in as an admin → **System Updates**.
3. Upload the release asset named `JARVIS_v1_FULL_UPDATE.zip`.
4. Validate and confirm the installer. The updater may need its systemd worker installed and running.
5. Allow Docker to build the new image; refresh the browser with Ctrl+Shift+R.

## Or install the staged ZIP over an existing checkout

Example for a typical Ubuntu account; adjust folder and filename:

```bash
cd "$HOME/jarvis"
mkdir -p data/updates
cp "$HOME/JARVIS_v1_FULL_UPDATE.zip" data/updates/
python3 apply_update.py --file data/updates/JARVIS_v1_FULL_UPDATE.zip
```

Type `APPLY` to approve. The script backs up replaced source files under `data/update_backups/` and calls `docker compose up -d --build`. If Docker build fails due to DNS, inspect logs rather than deleting volumes. The source-file backup isn't a substitute for your private-data backup.

## Source-code Git clone updates

If you initially installed using `git clone`, you may update tracked source with `git pull --ff-only`, then `docker compose up -d --build`. Back up first; git-based updates are not handled by the ZIP updater and local code changes can block `git pull`.

## Do NOT

- Never upload `.env`, `data/`, database files, voice samples, or printer credentials to GitHub.
- Never run `docker compose down -v` when preserving data.
- Never rename the GitHub source ZIP to look like an updater ZIP; its extra folders are not accepted by the updater.
