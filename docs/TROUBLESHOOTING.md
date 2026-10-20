# Troubleshooting

**Show service state:**

```bash
docker compose ps
docker compose logs --tail=80 jarvis
docker compose logs --tail=80 voice
docker compose logs --tail=80 browser
```

**Browser worker unavailable:** Rebuild `docker compose build --no-cache browser`, then `docker compose up -d --force-recreate --no-deps browser`. The browser image must install Python Playwright matching its base image. If DNS resolution fails during build, fix Docker DNS/connectivity before retrying.

**AI host cannot be resolved:** Test DNS from host and from `jarvis` container; verify provider API key and configured model. The browser worker and hosted AI provider are separate services.

**Microphone blocked:** For a remote browser, use HTTPS with a trusted certificate. Open and focus JARVIS browser tab, allow mic, and opt into wake listening. Browsers can block speech autoplay until you've interacted with the page.

**Weather missing:** Appearance → Weather settings; save valid coordinates; check internet access to Open-Meteo. Weather is optional and outdoors only.

**Printers missing:** Ensure private `config/printers.json` exists, real LAN addresses and serials are configured, access-code env keys are defined, and the jarvis container was restarted after editing `.env`.

**Forgot initial password:** See `reset_password.py` to reset an existing admin via the host. Don't post database files or terminal outputs containing passwords.

**Updates not applying:** Verify `data/updates/`, the ZIP is the special updater-compatible asset (not the GitHub source archive), the account has permission to run Docker, and the updater worker is active if using the web interface.
