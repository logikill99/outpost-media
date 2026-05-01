# Outpost Media — Deployment Guide

Complete setup guide for deploying Outpost Media on a Raspberry Pi Zero 2W.

---

## Hardware Requirements

| Item | Notes |
|------|-------|
| Raspberry Pi Zero 2W | The only officially tested target |
| MicroSD card | 64GB+ Class A1 recommended; 256GB works fine |
| UPS HAT (optional) | SugarPi or similar — essential for outdoor/event use |
| USB power bank | 20,000+ mAh for all-day events |
| Heatsink | Mandatory — the Zero 2W throttles hard under sustained load without one |

---

## 1. Flash the SD Card

Use **Raspberry Pi Imager** or `dd`. Recommended OS: **Raspberry Pi OS Lite 64-bit (Bookworm or Trixie)**.

In Raspberry Pi Imager, under Advanced Options before flashing:
- Set hostname: `outpost`
- Enable SSH with password authentication
- Set username/password (e.g. `outpost` / your chosen password)
- Configure WiFi for your home/setup network so the Pi is reachable on first boot

---

## 2. Pre-boot Config (before first boot)

Mount the boot partition and apply these tweaks before first boot. On macOS the partition mounts as `bootfs`; on Linux mount `/dev/sdX1`.

### `/boot/firmware/config.txt` — append at end

```ini
# Performance + headless
gpu_mem=16
dtoverlay=disable-bt

# USB gadget ethernet (for direct SSH from a host machine)
dtoverlay=dwc2
```

### `/boot/firmware/cmdline.txt` — append to the existing single line (no newline)

```
modules-load=dwc2,g_ether
```

> **Note:** `cmdline.txt` must be a single line. Append with a space before `modules-load`.

---

## 3. First Boot — Find the Pi

Boot the Pi. It will connect to your WiFi and be reachable by hostname:

```bash
ssh outpost@outpost.local
# or find IP via your router / nmap -sn 192.168.x.0/24
```

---

## 4. Clone the Repo

```bash
git clone https://github.com/logikill99/outpost-media.git ~/outpost-media
cd ~/outpost-media
```

---

## 5. Configure Secrets

```bash
cp .env.example .env
nano .env   # or your preferred editor
```

Fill in real values:

```env
SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
ADMIN_PASSWORD=<your admin panel password>
CTF_FLAG_WELCOME=FLAG{your_flag_here}
CTF_FLAG_PITWALL=FLAG{your_flag_here}
CTF_FLAG_STEG=FLAG{your_flag_here}
CTF_FLAG_CAESAR=FLAG{your_flag_here}
CTF_FLAG_BLACKBOX=FLAG{your_flag_here}
CTF_FLAG_FINALLAP=FLAG{your_flag_here}
```

> The `FINALLAP` flag is intended to be derived from the others — see CTF challenge descriptions.

---

## 6. Configure the AP

Edit `config/hostapd.conf` and set your SSID and WiFi password:

```
ssid=YourEventSSID
wpa_passphrase=YourWiFiPassword
```

> The channel is set to 6 (2.4 GHz). The Zero 2W is single-band; do not change `hw_mode`.

---

## 7. Run Setup

```bash
sudo bash scripts/setup.sh
```

This script:
- Installs `hostapd`, `dnsmasq`, `Caddy`, Python venv + dependencies
- Installs all config files to `/etc/`
- Writes and enables five systemd units: `outpost-network`, `outpost`, `outpost-caddy`, `hostapd`, `dnsmasq`
- Tells NetworkManager to leave `wlan0` alone
- Creates `instance/` and `media/videos/` directories

---

## 8. Add Content

### Movies

Encode video files on a capable machine (not the Pi — it can't encode fast enough):

```bash
ffmpeg -i "input.mkv" \
  -vf scale=1280:720 \
  -c:v libx264 -preset slow -crf 23 \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  "output.mp4"
```

Copy encoded files to `media/videos/` on the Pi. Caddy serves these directly with range request support — do not proxy video through Flask.

### Library articles

`scrape_wiki.py` (gitignored — run locally with internet access) populates `content/library/`. Sync to Pi with `rsync` or `scp`.

---

## 9. Reboot

```bash
sudo reboot
```

After reboot, the Pi is in AP mode. Connect any device to the SSID and navigate to **http://10.0.0.1** — the captive portal should appear automatically.

---

## 10. Verify Services

```bash
systemctl status outpost-network outpost outpost-caddy hostapd dnsmasq
journalctl -u outpost -f   # Flask app logs
```

---

## USB Gadget Ethernet (Management Bridge)

If you configured USB gadget mode in step 2, the Pi presents as a USB ethernet adapter when plugged into a host machine. This gives you SSH access even when the Pi is in AP mode and off your home network.

### On the Pi — configure a static IP for `usb0`

NetworkManager is already running on the Pi and manages `usb0`. Add a static connection with `nmcli`:

```bash
sudo nmcli con add type ethernet ifname usb0 con-name usb-static ip4 10.55.55.2/24 gw4 10.55.55.1
sudo nmcli con up usb-static
```

This persists across reboots — NM will bring up `usb0` at `10.55.55.2` automatically.

> **Note:** Do not also run `systemctl enable systemd-networkd` — that creates a conflict with NM and the interface ends up with no IP.

### On the host machine (fembox) — bring up the interface

Find the USB ethernet interface name (it will be `enx<mac>`):

```bash
ip link show | grep enx
```

Configure it (replace `enxb63a642c5ad8` with your interface name):

```bash
sudo ip link set enxb63a642c5ad8 up
sudo ip addr add 10.55.55.1/24 dev enxb63a642c5ad8
```

To make this persistent, create `/etc/systemd/network/10-pi-usb.network` on the host:

```ini
[Match]
MACAddress=b6:3a:64:2c:5a:d8

[Network]
Address=10.55.55.1/24
```

### SSH over USB

```bash
ssh outpost@10.55.55.2
```

---

## Network Topology

```
[Client device] ──WiFi──▶ wlan0 (Pi, 10.0.0.1)
                              │
                              ├── hostapd       (AP, WPA2-PSK, 2.4 GHz ch6)
                              ├── dnsmasq       (DHCP 10.0.0.10–30, wildcard DNS)
                              └── Caddy :80
                                   ├── captive portal probes → /portal
                                   ├── /socket.io/*          → Flask :5000
                                   ├── /api/* /admin/* /ctf/* /chat /movies
                                   │   /games /library /schedule /info* /portal
                                   │                         → Flask :5000
                                   ├── /media/*              → file_server (range)
                                   ├── /static/*             → file_server
                                   └── *                     → Flask :5000

[Host machine] ──USB──▶ usb0 (Pi, 10.55.55.2)   ← management only
                              └── enx<mac> (host, 10.55.55.1)
```

---

## Admin Panel

Available at **http://10.0.0.1/admin** once the AP is up.

Password is set by `ADMIN_PASSWORD` in `.env`.

---

## Systemd Services Reference

| Service | Description |
|---------|-------------|
| `outpost-network` | Oneshot — assigns 10.0.0.1/24 to wlan0 |
| `hostapd` | WiFi AP |
| `dnsmasq` | DHCP + wildcard DNS |
| `outpost` | Flask + SocketIO app on :5000 |
| `outpost-caddy` | Caddy reverse proxy on :80 |

All five are enabled and start on boot after `sudo bash scripts/setup.sh && sudo reboot`.

---

## Troubleshooting

**AP doesn't come up after reboot**
- Check: `journalctl -u hostapd -u outpost-network --no-pager -n 30`
- Common cause: NetworkManager is managing wlan0 and racing with hostapd. Confirm `/etc/NetworkManager/conf.d/outpost-unmanaged.conf` exists.

**Flask app crashes on start**
- Check: `journalctl -u outpost -n 50`
- Common cause: missing `.env` file. Run `cp .env.example .env` and fill in values.

**Captive portal doesn't appear on iOS/Android**
- dnsmasq must be running and resolving all DNS to 10.0.0.1. Check: `systemctl status dnsmasq`
- Portal page must be valid HTML and work without JavaScript (stripped-down WebView).

**Video doesn't seek / buffering**
- Caddy serves video with range requests. If you accidentally proxy video through Flask, seek will break. Check Caddyfile — `/media/*` must use `file_server`, not `reverse_proxy`.

**SQLite errors under load**
- The app sets WAL mode and a 5-second busy timeout. If you still see lock errors, the SD card I/O is the bottleneck. Consider a faster card (U3 / A2 rated).
