#!/usr/bin/env bash
# ============================================================
#  mb-firstboot.sh — MagicBridge first-boot finalize.
#
#  Runs ONCE on the first boot of a freshly-flashed card (guarded by a marker).
#  A golden .img is generic; this makes each unit unique + clean, then hands off
#  to WiFi onboarding:
#     1. OLED: "Please wait — first-time setup"
#     2. fresh SSH host keys      (never ship shared keys in an image)
#     3. fresh machine-id
#     4. clear any onboarding/identity state baked into the image
#        (saved WiFi, MAC-spoof .link files, net/stealth runtime config)
#     5. re-apply branding (OLED name, theme)
#     6. mark done; mb-portal then raises the setup hotspot if there's no network
#
#  Filesystem auto-expand is handled by the image's own first-boot resize
#  (pishrink / PiKVM), not here — see docs/IMAGING.md.
# ============================================================
set +e

MARKER="/var/lib/magicbridge/.mb-firstboot-done"   # removed by image-prep before snapshot
OLED="/usr/local/bin/mb-oled-msg"
LOG="/run/mb-firstboot.log"
exec >> "$LOG" 2>&1
echo "[$(date)] mb-firstboot starting"

[ -e "$MARKER" ] && { echo "already finalized — nothing to do"; exit 0; }

mb_rw(){ command rw 2>/dev/null || mount -o remount,rw / ; }
mb_ro(){ command ro 2>/dev/null || mount -o remount,ro / ; }

# 1) tell the user we're working
[ -x "$OLED" ] && "$OLED" "MagicBridge" "Please wait" "first-time setup" 2>/dev/null

mb_rw

# 2) fresh SSH host keys
echo "regenerating SSH host keys"
rm -f /etc/ssh/ssh_host_* 2>/dev/null
ssh-keygen -A >/dev/null 2>&1

# 3) fresh machine-id
echo "resetting machine-id"
rm -f /etc/machine-id /var/lib/dbus/machine-id 2>/dev/null
systemd-machine-id-setup >/dev/null 2>&1
ln -sf /etc/machine-id /var/lib/dbus/machine-id 2>/dev/null

# 4) clear onboarding / identity state that a golden image must not carry
echo "clearing baked-in onboarding state"
printf 'ctrl_interface=/run/wpa_supplicant\nupdate_config=1\ncountry=US\n' \
    > /etc/wpa_supplicant/wpa_supplicant-wlan0.conf 2>/dev/null
rm -f /etc/systemd/network/70-mb-*.link 2>/dev/null        # MAC-spoof persistence
rm -f /var/lib/magicbridge/net.json /var/lib/magicbridge/stealth.json \
      /var/lib/magicbridge/stealth_auth.json /var/lib/magicbridge/agent.json 2>/dev/null

# 5) re-apply branding (OLED text, theme) from branding.env
echo "applying branding"
python3 /opt/magicbridge/branding/apply_branding.py --root /opt/magicbridge >/dev/null 2>&1

# 6) mark done
mkdir -p "$(dirname "$MARKER")" 2>/dev/null
date > "$MARKER" 2>/dev/null

mb_ro
echo "[$(date)] mb-firstboot done — handing off to WiFi onboarding"
# Do NOT --resume the OLED here: if there's no network, mb-portal will show the
# "connect to hotspot" message next; if WiFi is already set, mb-portal resumes it.
exit 0
