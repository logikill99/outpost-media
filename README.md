# fieldday

A portable offline event server.

## What it is

fieldday is a self-contained web server that runs on a Raspberry Pi Zero 2W and creates its own WiFi access point. Connected devices get a captive portal that serves movies, a live chat room, browser games, a CTF challenge, and curated info pages (no internet required, everything is local). It is designed for places where cell service is saturated or absent, like racing events, campsites, festivals, or just a long weekend off-grid.

## Hardware

- Raspberry Pi Zero 2W
- 32GB+ microSD card (A1 rated, larger if you want a big movie library)
- USB-A power bank (any reasonable capacity, the Pi sips power)
- Optional: a small CRT or HDMI monitor for a status display
- Optional: a case and a heatsink (the Zero 2W can get warm under sustained load)

## Quick start

```bash
git clone https://github.com/yourname/fieldday.git
cd fieldday
cp .env.example .env
# edit .env and fill in SECRET_KEY, ADMIN_PASSWORD, and the CTF flags
sudo bash scripts/setup.sh
sudo reboot
```

After reboot the Pi broadcasts its SSID and serves the site at `http://10.0.0.1/`.

## Content setup

- Drop video files into `media/videos/`. Any `.mp4`, `.mkv`, or `.webm` is auto-discovered.
- Add metadata (title, year, description, genre) to `content/movies.json`. Files without metadata get a generated title from the filename.
- Run `python scrape_wiki.py` (with internet access, on your laptop) to populate the offline Wikipedia library under `content/library/`.
- Edit JSON files in `content/` to update info pages, schedules, standings, etc.

## Network

The Pi runs `hostapd` to broadcast its own SSID and `dnsmasq` to hand out DHCP leases in the `10.0.0.10` to `10.0.0.30` range. Wildcard DNS resolves every hostname to `10.0.0.1`, which makes captive-portal detection on iOS, Android, and Windows trigger automatically. Caddy fronts the static files and proxies the dynamic routes (`/api`, `/admin`, `/socket.io`) to the Flask process.

## License

MIT (see `LICENSE`). Bundled and dependent third-party software is listed in `THIRD_PARTY_NOTICES.md`.

## Disclaimer

fieldday is not affiliated with any racing series, sanctioning body, or event organizer. It is a personal hobby project.
