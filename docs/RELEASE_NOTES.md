# 🚀 JARVIS ONE v1 — Your Self-Hosted AI Command Center

**Your AI. Your Home. Your Control.**

Meet **JARVIS ONE**, a self-hosted cyber-cyan control dashboard for Linux enthusiasts, makers, and 3D printer owners. Bring voice interaction, AI chat, browser automation and Bambu printer telemetry under one screen.

### Highlights

- Animated neon-cyan command HUD and real CPU, RAM, storage and uptime stats
- Optional “Hey JARVIS” wake listening, random spoken greetings and next-command capture
- Hosted AI via your own NVIDIA or OpenRouter API credentials
- Live outdoor weather configured from the dashboard — no `.env` editing for coordinates
- Bambu Lab printer status, temperature and progress via LAN MQTT, with optional camera URLs
- User-selected time zones, family accounts, tasks and notes
- Dedicated Chromium Browser Control, Piper TTS, Whisper STT and update tools

### Downloads

**New installation:** Download/clone the GitHub source and follow `docs/INSTALL_UBUNTU.md`.  
**Existing installation:** Download `JARVIS_v1_FULL_UPDATE.zip`, back up your config, then use the built-in System Updates panel or `python3 apply_update.py --file ...`.

### Important before you install

- Works on an Ubuntu/Linux Docker host; no Windows desktop native installer.
- Requires your own cloud AI API key for hosted model chat and outbound internet to providers.
- Browser-based hands-free voice requires the browser tab open, user permission, and usually HTTPS from remote devices.
- Printer access codes, weather settings and voice data are **not** included.
- Keep the default HTTP port on a trusted LAN; do not expose it publicly.

MIT licensed. See README, configuration and security notes for details.
