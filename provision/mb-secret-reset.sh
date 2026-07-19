#!/usr/bin/env bash
# ============================================================
#  mb-secret-reset.sh — MagicBridge per-unit secret reset (PiKVM / kvmd).
#
#  Regenerates every secret that must be UNIQUE per physical unit, so a golden
#  image never ships shared credentials/keys — which would let units impersonate
#  each other and be cross-linked (a hard break of the anonymity model).
#
#  Run once by mb-firstboot.sh on a flashed unit; safe to re-run. Adapted (idea,
#  not code) from DIY's mb-secret-reset: that stack is NetworkManager +
#  /etc/magicbridge; here it's kvmd + wpa_supplicant + /etc/kvmd.
# ============================================================
set +e
info(){ echo "[$(date)] secret-reset: $*"; }
mb_rw(){ command rw 2>/dev/null || mount -o remount,rw / ; }
mb_ro(){ command ro 2>/dev/null || mount -o remount,ro / ; }
mb_rw

# 1. SSH host keys — otherwise every unit shares one host identity.
info "regenerating SSH host keys"
rm -f /etc/ssh/ssh_host_*
ssh-keygen -A >/dev/null 2>&1

# 2. machine-id — a cross-linkable per-install identifier.
info "regenerating machine-id"
rm -f /etc/machine-id /var/lib/dbus/machine-id
systemd-machine-id-setup >/dev/null 2>&1
ln -sf /etc/machine-id /var/lib/dbus/machine-id 2>/dev/null

# 3. kvmd TLS cert/key (nginx + vnc) — self-signed, must be unique per unit.
for d in /etc/kvmd/nginx/ssl /etc/kvmd/vnc/ssl; do
    if [ -f "$d/server.key" ] || [ -f "$d/server.crt" ]; then
        info "regenerating TLS certificate in $d"
        openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
            -keyout "$d/server.key" -out "$d/server.crt" \
            -subj "/CN=magicbridge.local" \
            -addext "subjectAltName=DNS:magicbridge.local,IP:127.0.0.1" >/dev/null 2>&1
        chmod 600 "$d/server.key" 2>/dev/null
        chown kvmd-nginx: "$d/server.key" "$d/server.crt" 2>/dev/null
    fi
done

# 4. Auth back to defaults + drop our secret/identity state (no baked creds/keys).
# Default login is magicbridge/magicbridge (kept in sync with kvmd.json below,
# which the sidecars use to call kvmd's API). The stealth panel default password
# ("stealthbridge") comes from /etc/magicbridge/stealth_auth.json — we only clear
# the per-unit override in the writable state dir so it falls back to that default.
if command -v kvmd-htpasswd >/dev/null 2>&1; then
    info "resetting kvmd login to default magicbridge"
    printf 'magicbridge\nmagicbridge\n' | kvmd-htpasswd set magicbridge >/dev/null 2>&1 \
        || echo magicbridge | kvmd-htpasswd set magicbridge >/dev/null 2>&1
    kvmd-htpasswd del admin >/dev/null 2>&1 || true
fi
printf '{\n  "user": "magicbridge",\n  "passwd": "magicbridge",\n  "base": "https://127.0.0.1/api"\n}\n' \
    > /etc/magicbridge/kvmd.json 2>/dev/null
chmod 600 /etc/magicbridge/kvmd.json 2>/dev/null
: > /etc/kvmd/totp.secret 2>/dev/null
rm -f /var/lib/magicbridge/net.json /var/lib/magicbridge/stealth.json \
      /var/lib/magicbridge/stealth_auth.json /var/lib/magicbridge/agent.json 2>/dev/null

# 5. USB gadget serial — drop our OTG override so a FRESH realistic serial is
#    generated on the next gadget build (the stealth service re-emits one).
info "clearing USB identity override (serial regenerates)"
rm -f /etc/kvmd/override.d/90-magicbridge-otg.yaml 2>/dev/null

# 6. Saved WiFi + MAC persistence — provision fresh, don't join the builder's net.
info "clearing saved WiFi + MAC persistence"
printf 'ctrl_interface=/run/wpa_supplicant\nupdate_config=1\ncountry=US\n' \
    > /etc/wpa_supplicant/wpa_supplicant-wlan0.conf 2>/dev/null
rm -f /etc/systemd/network/70-mb-*.link 2>/dev/null
# Reset hostname to a placeholder tell so mb-anon-defaults regenerates a fresh
# per-unit DESKTOP-XXXXXXX on this clone (the builder's name must not persist).
info "resetting hostname (regenerated per unit)"
hostnamectl set-hostname magicbridge 2>/dev/null
printf 'magicbridge\n' > /etc/hostname 2>/dev/null

# 7. Tailscale — don't inherit the builder's node identity.
info "clearing Tailscale state"
tailscale logout >/dev/null 2>&1
systemctl stop tailscaled >/dev/null 2>&1
rm -f /var/lib/tailscale/tailscaled.state 2>/dev/null

# 8. RAM logs / provisioning leftovers.
rm -f /run/mb-*.log /tmp/mb-* 2>/dev/null

mb_ro
info "done"
exit 0
