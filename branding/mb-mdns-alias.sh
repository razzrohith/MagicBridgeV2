#!/usr/bin/env bash
# Publish MagicBridgeV2 mDNS aliases (e.g. magicbridge.local) independent of
# the system hostname, via avahi. Self-heals a masked avahi (lesson from V1).
set -euo pipefail
# shellcheck disable=SC1091
[ -f /opt/magicbridge/branding/branding.env ] && source /opt/magicbridge/branding/branding.env
ALIASES="${MB_MDNS_ALIASES:-magicbridge}"

# unmask + start avahi if a previous image left it masked
systemctl unmask avahi-daemon.service avahi-daemon.socket 2>/dev/null || true
systemctl enable --now avahi-daemon.service 2>/dev/null || true

IP="$(hostname -I | awk '{print $1}')"
for name in $ALIASES; do
    /usr/bin/avahi-publish -a -R "${name}.local" "$IP" &
done
wait
