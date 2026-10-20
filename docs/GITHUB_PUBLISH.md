# Publish JARVIS ONE to GitHub

Recommended **repository name:** `jarvis-one-ai-command-center`  
**Display name:** JARVIS ONE — Your Self-Hosted AI Command Center  
**Description:** A self-hosted, voice-enabled AI command center with a neon HUD, browser tools, live weather, and Bambu Lab 3D-printer monitoring.  
**Topics:** `jarvis`, `self-hosted`, `ai-assistant`, `docker`, `ubuntu`, `voice-assistant`, `smart-home`, `3d-printing`, `bambu-lab`, `fastapi`, `playwright`, `openrouter`, `nvidia`

## Before publishing

Read [SECURITY.md](../SECURITY.md). The provided source bundle contains no private `.env` or database. If you edit it locally, check with `git status --short` and avoid `git add -f` on ignored files. Do not publish your running server's `~/jarvis` folder as-is.

## Create the repo from the source ZIP

1. Create a **new empty** GitHub repository called `jarvis-one-ai-command-center` (do not auto-create README or license; they're supplied).
2. Extract `JARVIS_ONE_v1_GITHUB_SOURCE.zip` into a folder on your PC or Ubuntu server and `cd` into the extracted folder.
3. From a machine with Git installed:

```bash
git init -b main
git add .
git status --short
git commit -m "Release JARVIS ONE v1"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/jarvis-one-ai-command-center.git
git push -u origin main
```

Replace `YOUR_GITHUB_USERNAME` with your real account name. GitHub may ask you to authenticate using Git Credential Manager, a token, or SSH; **do not paste credentials into chat or commit them**.

## Publish downloadable v1 release

1. Open your new repo → **Releases** → **Draft a new release**.
2. Create tag `v1` from branch `main`.
3. Set title to **JARVIS ONE v1 — Your Self-Hosted AI Command Center**.
4. Attach **`JARVIS_v1_FULL_UPDATE.zip`** as the updater-compatible release download (the source code is already on the repository; GitHub automatically offers source ZIP/TAR files).
5. Paste `docs/RELEASE_NOTES.md` into the release description and publish.

The official **release file is for existing installations**; first-time users should follow README.md and clone the repository. The GitHub source ZIP contains project docs and CI, which the in-app updater will reject.

Optional: pin the README screenshot, add topics and repository description, enable Issues and Discussions, and post the promotional copy from `docs/PROMO_KIT.md`.
