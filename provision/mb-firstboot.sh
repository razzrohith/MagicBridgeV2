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

# 3. realistic, STABLE per-unit hostname (DESKTOP-XXXXXXX) + WiFi MAC (real vendor
#    OUI via a networkd .link). mb-secret-reset just cleared these, so this
#    generates fresh unique values for THIS unit; idempotent, so they then stay put.
bash "$ROOT/provision/mb-anon-defaults.sh"

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
