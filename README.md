# outpost-media

A portable offline event server for places where cell service is nonexistent or saturated.

Runs on a Raspberry Pi Zero 2W, broadcasts its own WiFi AP, and serves a self-contained site with movies, a live chat room, browser games, an offline library, and a CTF challenge. No internet required — everything is local.

---

## Hardware

- Raspberry Pi Zero 2W
- 64GB+ microSD card (A1 rated; larger if you want a big movie library)
- USB power bank (the Pi draws ~2W under load)
- Heatsink recommended — the Zero 2W throttles under sustained load without one

---

## Quick start

```bash
git clone https://github.com/logikill99/outpost-media.git
cd outpost-media
cp .env.example .env
# fill in SECRET_KEY, ADMIN_PASSWORD, and the six CTF_FLAG_* values
nano config/hostapd.conf  # set your SSID (open network by default)
sudo bash scripts/setup.sh
sudo reboot
```

After reboot the Pi broadcasts its SSID and serves the site at `http://10.0.0.1/`. Any connected device's captive portal prompt will point there automatically.

See [SETUP.md](SETUP.md) for the full deployment guide including pre-boot config, content setup, and troubleshooting.

---

## Content

**Movies** — drop encoded `.mp4`/`.mkv`/`.webm` files into `media/videos/`. They're auto-discovered at runtime. Add metadata (title, year, description) to `content/movies.json` for nicer display; unmatched files fall back to a generated title.

Encode on a capable machine (not the Pi):

```bash
ffmpeg -i input.mkv -vf scale=1280:720 -c:v libx264 -preset slow -crf 23 \
  -c:a aac -b:a 128k -movflags +faststart output.mp4
```

**Library** — run `python scrape_wiki.py` (with internet, on your laptop) to populate `content/library/` with offline Wikipedia articles.

**F1 data** — standings, driver profiles, and schedule live in `content/`. Edit the JSON files directly or replace them before the event.

---

## Local development

You don't need a Pi, hostapd, dnsmasq, or Caddy to work on the app. Flask serves everything directly and the full site is usable on localhost. Nothing is installed to the system and nothing runs as a daemon — it's a foreground process you stop with `Ctrl+C`.

**Requirements:** Python 3.12 is recommended. Newer versions (3.13+) may have compatibility issues with `eventlet`.

### First-time setup

```bash
git clone https://github.com/logikill99/outpost-media.git
cd outpost-media

python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip wheel
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# Any values work for local dev — SECRET_KEY, ADMIN_PASSWORD, and the
# six CTF_FLAG_* values just need to be non-empty.
```

### Run it

```bash
./scripts/dev.sh
```

That's the one-command path: it activates `.venv`, loads `.env`, and starts the Flask + SocketIO app on `http://localhost:5000` (or whatever `PORT` you set in `.env`). `Ctrl+C` to stop.

> **macOS note:** Control Center / AirPlay Receiver listens on port 5000 by default. Either set `PORT=5001` in `.env`, or disable the AirPlay Receiver under System Settings → General → AirDrop & Handoff.

If you'd rather run it manually:

```bash
.venv/bin/python run.py
# or: source .venv/bin/activate && python run.py
```

The SQLite database (`instance/outpost.db`) initializes automatically on first run and gets seeded with the CTF challenges from your `.env` flags.

### Differences from the Pi

- **No captive portal** — navigate directly to `http://localhost:5000`
- **No AP or DHCP** — the network stack (hostapd/dnsmasq) is Pi-only and irrelevant locally
- **Caddy is optional** — Flask serves static files fine in dev. If you want to test video seek/range requests accurately, put Caddy in front, but it's not required
- **Admin panel** is at `http://localhost:5000/admin`

---

## Managing the Pi over USB (recommended)

When the Pi is in AP mode it's off your home network, which makes SSH over WiFi impossible from a host machine. The better approach is USB ethernet gadget mode — the Pi presents as a USB network adapter when plugged into any computer, giving you a direct SSH connection regardless of what the WiFi radio is doing.

### One-time setup

**1. Pre-boot config** (edit the SD card before first boot, or edit in place and reboot):

In `/boot/firmware/config.txt`, add at the end:
```
dtoverlay=dwc2
```

In `/boot/firmware/cmdline.txt`, append to the existing single line (no newline):
```
 modules-load=dwc2,g_ether
```

**2. On the Pi** — configure a static IP for the USB interface. Run this once after first boot (while the Pi is still on your home network, or via the AP):

```bash
sudo nmcli con add type ethernet ifname usb0 con-name usb-static ip4 10.55.55.2/24 gw4 10.55.55.1
sudo nmcli con up usb-static
```

This persists across reboots. NetworkManager brings `usb0` up at `10.55.55.2` automatically on every boot.

> Don't also run `systemctl enable systemd-networkd` — that conflicts with NetworkManager and leaves the interface unconfigured.

**3. On the host machine** — find the USB ethernet interface and bring it up:

```bash
# find the interface name (will be enx<mac> on Linux, something like en7 on macOS)
ip link show | grep enx       # Linux
networksetup -listallhardwareports  # macOS

# Linux
sudo ip link set enx<yourmac> up
sudo ip addr add 10.55.55.1/24 dev enx<yourmac>

# macOS — set manually in System Settings > Network > USB Ethernet > Manual
# IP: 10.55.55.1, subnet: 255.255.255.0
```

To make the host side persistent on Linux, create `/etc/systemd/network/10-pi-usb.network`:
```ini
[Match]
MACAddress=<mac of the enx interface>

[Network]
Address=10.55.55.1/24
```

**4. SSH in:**

```bash
ssh outpost@10.55.55.2
```

Works whether the Pi is in AP mode, connected to your home network, or anything else.

---

## Network topology

```
[Client device] ──WiFi──▶ wlan0 (Pi, 10.0.0.1)
                              ├── hostapd       AP, open network
                              ├── dnsmasq       DHCP + wildcard DNS
                              └── Caddy :80     reverse proxy + static files
                                   └── Flask :5000

[Host machine]  ──USB───▶ usb0 (Pi, 10.55.55.2)   ← management only
                              └── enx<mac> (host, 10.55.55.1)
```

---

## Admin panel

`http://10.0.0.1/admin` — password set by `ADMIN_PASSWORD` in `.env`.

---

## License

MIT — see `LICENSE`. Bundled third-party software is listed in `THIRD_PARTY_NOTICES.md`.

## Disclaimer

Not affiliated with any racing series, sanctioning body, or event organizer. Personal hobby project.
