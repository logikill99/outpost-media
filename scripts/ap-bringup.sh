#!/bin/bash
# Outpost AP bringup — configures wlan0 as 10.0.0.1 before hostapd/dnsmasq start.
# Runs as oneshot at boot via outpost-network.service.

set -e

IFACE=wlan0
IP=10.0.0.1/24

echo "[outpost-network] Bringing up $IFACE as AP interface..."

# Flush any existing config on the interface
ip addr flush dev $IFACE 2>/dev/null || true
ip link set $IFACE up

# Assign static IP
ip addr add $IP dev $IFACE

echo "[outpost-network] $IFACE is up at $IP"
