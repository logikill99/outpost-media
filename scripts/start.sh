#!/usr/bin/env bash
# Start all Outpost services (run as root).
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "sudo required" >&2; exit 1; fi
systemctl restart dhcpcd || true
systemctl restart hostapd
systemctl restart dnsmasq
systemctl restart outpost
systemctl restart caddy
systemctl --no-pager status outpost caddy hostapd dnsmasq | head -n 60
