# Open-source release prep — change summary

This pass prepared outpost-media for public release on GitHub. No Flask app logic was modified; changes are limited to compliance, configuration, documentation, and secrets hygiene.

## Files added

- `.gitignore` — replaced. Ignores `instance/`, `.env`, `__pycache__/`, `*.pyc`, `media/videos/`, `media/movies/`, `content/library/wikipedia/`, virtualenvs, `*.egg-info`, OS junk, logs, all SQLite files, and the local-only `scrape_wiki.py` and `DEVLOG.md`.
- `.env.example` — template for `SECRET_KEY`, `ADMIN_PASSWORD`, and the six `CTF_FLAG_*` values.
- `LICENSE` — MIT License, copyright 2026 Matthew Levin.
- `THIRD_PARTY_NOTICES.md` — bundled and dependent OSS with their licenses.
- `README.md` — project overview, hardware list, quick start, content setup, network notes, license, and disclaimer.

## Files updated

- `app/config.py` — replaced. Loads `.env` via `python-dotenv`, pulls `SECRET_KEY`, `ADMIN_PASSWORD`, and CTF flags from environment variables, and exposes a `CTF_FLAGS` dict keyed by challenge slug.
- `app/__init__.py` — only the six hardcoded CTF flag strings in `_seed_initial_data` were swapped for `app.config["CTF_FLAGS"].get(slug, "FLAG{placeholder}")`. No other logic changed.
- `config/hostapd.conf` — `ssid` set to `YourEventSSID`, `wpa_passphrase` set to `YourWiFiPassword` (placeholders for operators).
- `ARCHITECTURE.md` — rewritten as a generic architecture doc covering network topology, data model, content pipeline, systemd deployment, and Pi Zero 2W constraints. All event-specific references removed.
- `scripts/setup.sh` — rewritten. Detects repo dir, installs system packages, installs Caddy from the official apt repo, sets up the venv, places hostapd/dnsmasq/Caddy configs, writes the NetworkManager unmanaged drop-in, creates three systemd units (`outpost-network`, `outpost`, `outpost-caddy`), enables services, creates runtime dirs, and warns on missing `.env`.
- `requirements.txt` — `python-dotenv==1.0.1` added.

## Secrets hygiene

- No secrets are committed. Real `SECRET_KEY`, admin password, and CTF flag values are read from `.env` (gitignored).
- The previous hardcoded SSID, WiFi passphrase, admin password, secret key, and CTF flag plaintexts were removed from tracked files.
