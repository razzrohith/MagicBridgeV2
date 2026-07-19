#!/usr/bin/env bash
# ============================================================
#  mb-firstboot.sh — MagicBridge first-boot finalize.
#
#  Runs ONCE on the first boot of a freshly-flashed card (marker-guarded). A
#  golden .img is generic; this makes each unit unique + anonymous, then hands
#  off to WiFi onboarding:
#     1. OLED: "Please wait — first-time setup"
#     2. per-unit secret reset  (mb-secret-reset.sh: SSH/TLS keys, machine-id,
#        auth->default, USB serial, cleared WiFi/Tailscale/identity state)
#     3. realistic default MAC  (real vendor OUI, not the CM4 dc:a6:32 tell)
#     4. realistic default EDID (a real Dell monitor, never a MagicBridge tell)
#     5. re-apply branding
#     6. mark done; mb-portal then raises the setup hotspot if there's no network
#
#  Filesystem auto-expand is the image's own first-boot resize, not here.
# ============================================================
set +e

MARKER="/var/lib/magicbridge/.mb-firstboot-done"   # removed by image-prep before snapshot
ROOT="/opt/magicbridge"
OLED="/usr/local/bin/mb-oled-msg"
LOG="/run/mb-firstboot.log"
exec >> "$LOG" 2>&1
echo "[$(date)] mb-firstboot starting"

[ -e "$MARKER" ] && { echo "already finalized — nothing to do"; exit 0; }

mb_rw(){ command rw 2>/dev/null || mount -o remount,rw / ; }
mb_ro(){ command ro 2>/dev/null || mount -o remount,ro / ; }

# 1. tell the user we're working
[ -x "$OLED" ] && "$OLED" "MagicBridge" "Please wait" "first-time setup" 2>/dev/null

# 2. per-unit secrets (its own rw/ro handling)
if [ -x "$ROOT/provision/mb-secret-reset.sh" ]; then
    echo "running mb-secret-reset"
    bash "$ROOT/provision/mb-secret-reset.sh"
fi

mb_rw

# 3. realistic default MAC — the CM4's real OUI (dc:a6:32) is a "this is a Pi"
#    network tell. Pick a real consumer-vendor OUI + random NIC portion, persisted
#    via a systemd-networkd .link so udev applies it at boot BEFORE wlan0
#    associates (no reconnect churn, no brick).
OUIS=(a0:88:b4 3c:58:c2 34:41:5d e4:a4:71 f8:94:c2 48:2a:e3 d0:c6:37 c8:2b:96)
oui=${OUIS[$((RANDOM % ${#OUIS[@]}))]}
mac=$(printf '%s:%02x:%02x:%02x' "$oui" $((RANDOM%256)) $((RANDOM%256)) $((RANDOM%256)))
echo "default MAC -> $mac"
printf '[Match]\nOriginalName=wlan0\n\n[Link]\nMACAddressPolicy=none\nMACAddress=%s\n' "$mac" \
    > /etc/systemd/network/70-mb-wlan0.link 2>/dev/null

# 4. realistic default monitor EDID identity (a real Dell), so the target never
#    reads "MagicBridge"/"PiKVM"/a capture-card tell. Identity fields only.
if command -v kvmd-edidconf >/dev/null 2>&1; then
    ser=$(tr -dc A-Z </dev/urandom 2>/dev/null | head -c2)
    monser=$(printf 'CN%05d%s' $((RANDOM % 100000)) "${ser:-ZA}")
    echo "default EDID -> DELL P2419H / $monser"
    kvmd-edidconf --set-mfc-id DEL --set-monitor-name "DELL P2419H" \
        --set-product-id 16473 --set-serial $((RANDOM * RANDOM + 1)) \
        --set-monitor-serial "$monser" --apply >/dev/null 2>&1
fi

# 5. re-apply branding (OLED text, theme) from branding.env
echo "applying branding"
python3 "$ROOT/branding/apply_branding.py" --root "$ROOT" >/dev/null 2>&1

# 6. mark done
mkdir -p "$(dirname "$MARKER")" 2>/dev/null
date > "$MARKER" 2>/dev/null

mb_ro
echo "[$(date)] mb-firstboot done — handing off to WiFi onboarding"
# Don't --resume the OLED here: mb-portal shows the "connect to hotspot" message
# next if there's no network, or resumes the normal display if WiFi is already set.
exit 0
