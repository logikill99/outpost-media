# outpost-media — Architecture

A portable offline event server: WiFi AP plus captive-portal web stack on a single Raspberry Pi Zero 2W.

---

## Network topology

```
[Client device] ──WiFi──▶ wlan0 (Pi, 10.0.0.1)
                              │
                              ├── hostapd       (AP, WPA2-PSK)
                              ├── dnsmasq       (DHCP 10.0.0.10–30, wildcard DNS → 10.0.0.1)
                              └── Caddy :80
                                   ├── /portal          → static portal.html
                                   ├── /api/*           → Flask :5000
                                   ├── /admin/*         → Flask :5000
                                   ├── /socket.io/*     → Flask :5000 (WebSocket)
                                   ├── /media/videos/*  → file_server (range requests)
                                   ├── /static/*        → file_server
                                   └── *                → Flask :5000
```

`dnsmasq` resolves every DNS query to the Pi, which makes Apple, Android, and Windows captive-portal probes (`/hotspot-detect.html`, `/generate_204`, `/ncsi.txt`, etc.) land on Caddy. Those probe paths redirect to `/portal`, the OS opens its captive network assistant, the user taps through to the full site.

---

## Application stack

| Layer | Component |
|---|---|
| AP | hostapd (2.4 GHz, WPA2-PSK) |
| DHCP/DNS | dnsmasq (wildcard A record) |
| HTTP front | Caddy (static + reverse proxy + WS proxy) |
| App server | Flask + Flask-SocketIO on eventlet (single process) |
| ORM | SQLAlchemy (Flask-SQLAlchemy) |
| Admin UI | Flask-Admin |
| Storage | SQLite (one file, WAL mode) |
| Frontend | Alpine.js + Video.js + Socket.IO client (all bundled, no CDN) |

The Flask app is a single eventlet worker. Concurrency comes from greenlets, not threads or processes. SocketIO uses the same process — there is no Redis or external message queue.

---

## Data model

All persistent data lives in a single SQLite file (`instance/outpost.db`).

- **Message** — chat messages. `id`, `username`, `channel`, `body`, `created_at`, `deleted`.
- **Challenge** — CTF challenge definitions. `id`, `slug`, `title`, `category`, `points`, `description`, `flag_hash` (SHA-256), `hint`, `active`. Flag plaintext is never stored; submissions are hashed and compared.
- **Solve** — per-user solves. `id`, `username`, `challenge_id`, `solved_at`, with a unique constraint on `(username, challenge_id)`.
- **Announcement** — admin broadcasts. `id`, `body`, `created_at`, `active`.

WAL mode and a 5-second busy timeout are set on every SQLite connection (see `app/__init__.py`). This lets readers and the writer coexist under chat load on slow SD-card I/O.

---

## Content pipeline

Content is served from two trees, both read at request time:

- `content/` — JSON data files (`movies.json`, `schedule.json`, `drivers.json`, etc.) and standings under `content/standings/`. The Flask app reads these with a small in-process TTL cache (5 minutes) so repeated page loads do not re-parse the same JSON.
- `content/library/` — offline reference articles. `scrape_wiki.py` populates this from Wikipedia (run on a laptop with internet, then sync to the Pi). The library is indexed by an `index.json` manifest and rendered as static HTML pages.

Movies live in `media/videos/`. The `/movies` route auto-discovers `.mp4`, `.mkv`, and `.webm` files there and merges any matching entries from `content/movies.json` to fill in titles, years, and descriptions. Unmatched files fall back to a title generated from the filename.

---

## Deployment (systemd)

`scripts/setup.sh` installs five services:

- `outpost-network.service` — oneshot. Runs `scripts/ap-bringup.sh` to set the static IP on `wlan0` and put the interface up. Ordered before everything else.
- `hostapd.service` — broadcasts the SSID. After `outpost-network`.
- `dnsmasq.service` — DHCP and wildcard DNS. After `outpost-network`.
- `outpost.service` — the Flask/SocketIO app (`venv/bin/python run.py`). After `outpost-network`.
- `outpost-caddy.service` — `caddy run --config /etc/caddy/Caddyfile`. After `outpost`.

NetworkManager is told to leave `wlan0` alone via a drop-in at `/etc/NetworkManager/conf.d/outpost-unmanaged.conf`. Without that, NM races with hostapd at boot and the AP fails to come up cleanly.

---

## Pi Zero 2W specific notes

- **512MB RAM.** The whole stack (kernel, hostapd, dnsmasq, Caddy, Python with eventlet, SQLite, Flask-Admin) runs in roughly 200–250MB under typical load. Avoid spawning extra worker processes; eventlet is the right choice here.
- **SD card I/O.** The bottleneck is almost always the SD card, not the CPU. WAL mode keeps SQLite writes from blocking reads. Video is served by Caddy with range requests so the kernel page cache does the heavy lifting; do not proxy video through Flask.
- **Single-process app server.** Flask-SocketIO needs sticky sessions for WebSockets. With one eventlet worker there is nothing to be sticky to, which sidesteps the entire problem. If you ever scale this out you will need a Redis message queue.
- **2.4 GHz only.** The Zero 2W radio is single-band and shares the antenna between AP and station modes; we run AP-only.
- **Headless.** Setting `gpu_mem=16` in `/boot/config.txt` reclaims about 48MB. Disabling Bluetooth (`dtoverlay=disable-bt`) frees a bit more and removes a service.
- **Captive portal.** `portal.html` must be valid HTML, work without JavaScript, and stay under ~10KB. The captive network assistant on iOS and Android is a stripped-down WebView and gets cranky about modern frontend bundles.

---

## Repository layout

```
outpost-media/
├── app/
│   ├── __init__.py        Flask app factory, routes, SQLite pragmas, seed data
│   ├── config.py          Config class, reads .env via python-dotenv
│   ├── models.py          SQLAlchemy models
│   ├── chat/              SocketIO handlers + REST endpoints
│   ├── ctf/               CTF API
│   ├── api/               misc API (status, announcements)
│   └── admin/             Flask-Admin views
├── static/                bundled JS, CSS, images, games
├── templates/             Jinja templates
├── content/               JSON data + offline library
├── media/videos/          movie files (gitignored)
├── ctf/challenges/        CTF challenge static assets
├── config/                hostapd.conf, dnsmasq.conf, Caddyfile
├── scripts/               setup.sh, ap-bringup.sh, helpers
├── instance/              SQLite DB (gitignored)
├── run.py                 entrypoint (creates app, starts SocketIO)
├── requirements.txt
├── .env.example
├── LICENSE
├── README.md
└── THIRD_PARTY_NOTICES.md
```
