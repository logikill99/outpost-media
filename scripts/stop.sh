#!/usr/bin/env bash
# Stop all Outpost services (run as root).
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "sudo required" >&2; exit 1; fi
systemctl stop caddy outpost dnsmasq hostapd || true
echo "Stopped: caddy, outpost, dnsmasq, hostapd"
