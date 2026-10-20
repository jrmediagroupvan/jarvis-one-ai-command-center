# Configuration reference

## Cloud AI providers

The dashboard uses NVIDIA or OpenRouter APIs **with your own keys**. Configure `NVIDIA_API_KEY=` / `OPENROUTER_API_KEY=` in private `.env`, then restart `jarvis` if changed. Admin-approved model identifiers must match what your provider offers. No AI subscription is included.

## Voice and microphone

Voice uses a separate Docker service with Whisper speech-to-text and Piper text-to-speech. In AI Chat, opt into **Hey JARVIS** wake listening and allow microphone access. A voice wake greeting is selected randomly, then the next command is recorded. The browser tab must stay open; remote HTTP LAN IPs normally cannot access the mic due to secure-context rules. Configure HTTPS with a trusted certificate for microphone access. Autoplay may require an initial user gesture. Browser wake detection works with short speech clips, not a low-power hardware hotword engine.

## Outdoor weather

**Appearance → Weather settings** allows admins to save latitude, longitude and optional label without changing `.env`. Values are stored privately in `data/weather.json` and use Open-Meteo when online. WEATHER_LAT/LON in `.env` are legacy fallback values. Indoor sensors are not connected.

## Time zone

**Appearance → Time zone** saves a per-account IANA zone such as `America/Vancouver`, or Automatic to use browser zone. Only display clocks are changed; host timers and OS time zone are not.

## Bambu Lab printers

Run `python3 setup.py` to create private `config/printers.json` from `config/printers.example.json`; fill in your own printer serial, LAN IP, and `access_code_env` reference. Set matching `BAMBU_X1C_CODE` or other environment entries in `.env`, then run `docker compose up -d --force-recreate jarvis`. The monitor subscribes to read-only LAN MQTT reports; it does not send printer control commands. Live camera preview requires a browser-compatible HTTP(S) camera URL and appropriate camera authorization. No cameras or devices are bundled.

**Security:** Some printer integrations use self-signed local printer certificates. Only configure trusted private LAN addresses. Do not expose printer brokers or camera feeds publicly.

## Browser Control

JARVIS controls a dedicated, server-hosted Chromium process, not the Windows/Chrome browser on your personal PC. URLs must be public HTTPS; internal IP/hostnames are blocked by the browser worker. Puppeteer/Playwright permissions are limited. Don't type credentials into browser automation unless you understand its security boundary.

## Plugins, accounts and updates

Admin/family accounts and preferences persist in `data/jarvis.db`. ZIP code updates are sensitive: install only versions from a trusted source. The in-app updater may require the systemd worker; read `install_update_service.sh` before running since it configures a host service and uses sudo.
