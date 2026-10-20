# Security and responsible deployment

JARVIS ONE v1 is a self-hosted/community project, **not a hardened public SaaS**. Run it on a trusted LAN or behind an HTTPS reverse proxy, access controls and appropriate firewall rules. The default Compose file publishes `8765` on host interfaces. Do **not** forward that port from the internet to your server.

- Passwords, access codes and AI keys belong in `.env`, never GitHub.
- Private account data, weather coordinates, voices and SQLite database belong in `data/`.
- Real printer configuration belongs in private `config/printers.json`; example config is fake.
- HTTP Basic credentials should only cross a trusted, encrypted connection. Configure HTTPS before remote access.
- Giving a user Docker control is equivalent to powerful host access; review updater actions and plugins before enabling them.
- Browser Control is an isolated Chromium worker limited to public HTTPS sites, but browsing arbitrary sites still creates risks.
- The printer LAN monitor uses a self-signed TLS exception for printer MQTT on trusted networks; do not expose printer endpoints.
- Update ZIPs can contain executable source code. Verify origin before installation.
- If filing an issue, redact IPs, keys, credentials, LAN camera frames, names and personal details.

To report a sensitive vulnerability, contact the repository maintainer through their preferred private disclosure channel once the repository is published. Do not publish working exploits or private secrets in GitHub Issues.
