#!/usr/bin/env bash
# outpost-media — reconcile the Pi's git tree with origin/main.
#
# Use this on the Pi when it has internet access. Common case: after
# pushing changes from a laptop and rsync'ing them to the Pi (which
# leaves the Pi's git working tree out of sync with its .git/), run
# this once and the Pi will match origin/main exactly — except for
# config/hostapd.conf, which is intentionally preserved (it holds
# the production SSID and WiFi password).
set -euo pipefail

cd "$(dirname "$0")/.."

if ! git diff --quiet -- config/hostapd.conf 2>/dev/null; then
  git stash push -m "outpost: preserve hostapd.conf" -- config/hostapd.conf
  STASHED=1
else
  STASHED=0
fi

git fetch origin
git reset --hard origin/main

if [[ $STASHED -eq 1 ]]; then
  git stash pop
fi

echo
echo "Sync complete. Working tree now matches origin/main (plus local hostapd.conf)."
echo
git status --short
