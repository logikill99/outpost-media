#!/usr/bin/env bash
# fieldday — first-run setup for Raspberry Pi Zero 2W (Raspberry Pi OS Bookworm/Bullseye).
# Run as root from the project root: sudo bash scripts/setup.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

# Detect repo dir. Prefer /home/pi/fieldday, else fall back to invoking user's home.
if [[ -d /home/pi/fieldday ]]; then
  REPO_DIR=/home/pi/fieldday
else
  REAL_USER="${SUDO_USER:-$(id -un)}"
  REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
  REPO_DIR="$REAL_HOME/fieldday"
fi
SOURCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$SOURCE_DIR" != "$REPO_DIR" ]]; then
  echo "Note: running from $SOURCE_DIR, configuring as $REPO_DIR"
  REPO_DIR="$SOURCE_DIR"
fi

echo "==> Updating apt and installing system packages"
apt-get update
apt-get install -y --no-install-recommends \
  python3-pip python3-venv \
  hostapd dnsmasq \
  curl gnupg \
  debian-keyring debian-archive-keyring apt-transport-https ca-certificates

echo "==> Installing Caddy from the official apt repo"
if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update
  apt-get install -y caddy
fi

echo "==> Creating Python venv and installing requirements"
if [[ ! -d "$REPO_DIR/venv" ]]; then
  python3 -m venv "$REPO_DIR/venv"
fi
"$REPO_DIR/venv/bin/pip" install --upgrade pip wheel
"$REPO_DIR/venv/bin/pip" install -r "$REPO_DIR/requirements.txt"

echo "==> Installing hostapd config"
install -m 644 "$REPO_DIR/config/hostapd.conf" /etc/hostapd/hostapd.conf
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd

echo "==> Installing dnsmasq config"
mkdir -p /etc/dnsmasq.d
install -m 644 "$REPO_DIR/config/dnsmasq.conf" /etc/dnsmasq.d/fieldday.conf

echo "==> Installing Caddyfile"
mkdir -p /etc/caddy
sed "s|/opt/outpost|$REPO_DIR|g" "$REPO_DIR/config/Caddyfile" > /etc/caddy/Caddyfile
chmod 644 /etc/caddy/Caddyfile

echo "==> Telling NetworkManager to leave wlan0 alone"
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/fieldday-unmanaged.conf <<'EOF'
[keyfile]
unmanaged-devices=interface-name:wlan0
EOF

echo "==> Writing systemd units"

cat > /etc/systemd/system/fieldday-network.service <<EOF
[Unit]
Description=fieldday — bring up wlan0 with static IP
Before=hostapd.service dnsmasq.service fieldday.service
Wants=network.target
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/env bash $REPO_DIR/scripts/ap-bringup.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/fieldday.service <<EOF
[Unit]
Description=fieldday — Flask + SocketIO app
After=fieldday-network.service
Requires=fieldday-network.service

[Service]
WorkingDirectory=$REPO_DIR
ExecStart=$REPO_DIR/venv/bin/python $REPO_DIR/run.py
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/fieldday-caddy.service <<EOF
[Unit]
Description=fieldday — Caddy front
After=fieldday.service
Requires=fieldday.service

[Service]
ExecStart=/usr/bin/caddy run --config /etc/caddy/Caddyfile
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo "==> Reloading systemd and enabling services"
systemctl daemon-reload
systemctl unmask hostapd
systemctl enable fieldday-network.service fieldday.service fieldday-caddy.service hostapd.service dnsmasq.service

echo "==> Creating runtime directories"
mkdir -p "$REPO_DIR/instance" "$REPO_DIR/media/videos"

echo "==> Checking for .env"
if [[ ! -f "$REPO_DIR/.env" ]]; then
  echo
  echo "WARNING: $REPO_DIR/.env does not exist."
  echo "  Copy the template and fill in real values before rebooting:"
  echo "    cp $REPO_DIR/.env.example $REPO_DIR/.env"
  echo "    \$EDITOR $REPO_DIR/.env"
  echo
fi

echo "==> Setup complete"
echo "    Repo dir:     $REPO_DIR"
echo "    SSID:         (set in $REPO_DIR/config/hostapd.conf)"
echo "    Reboot to bring up the AP and start serving:  sudo reboot"
echo "    Then connect to the SSID and visit http://10.0.0.1/"
