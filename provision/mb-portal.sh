#!/usr/bin/env bash
# ============================================================
#  MagicBridgeV2 WiFi provisioning AP (captive portal)
#
#  Boot service (mb-portal.service). If — and ONLY if — the device has
#  no working network after boot, it raises a "MagicBridge-Setup" open
#  hotspot + captive portal so you can enter WiFi credentials from a
#  phone, then reconnects and exits. Re-checks every boot (moving the
#  device to a new location just re-runs setup instead of stranding it).
#
#  Adapted for PiKVM OS (Arch + wpa_supplicant, read-only rootfs).
#  Recovery: SSH/console always works; this never touches a live link.
#  SSID: MagicBridge-Setup (open)   Portal: http://192.168.73.1/
# ============================================================
set +e   # never abort mid-teardown — stranding the radio is worse than any error

LOG="/var/lib/magicbridge/portal.log"
AP_SSID="MagicBridge-Setup"
AP_IP="192.168.73.1"
AP_IFACE="wlan0"
PORT=8080
PORTAL="/opt/magicbridge/provision/portal.py"
WIFI_FILE="/tmp/mb-provision-wifi"
TS_KEY="/tmp/mb-provision-tskey"
WPA_CONF="/etc/wpa_supplicant/wpa_supplicant-${AP_IFACE}.conf"
mkdir -p /var/lib/magicbridge 2>/dev/null
exec >> "$LOG" 2>&1
echo "[$(date)] mb-portal starting"

rw(){ command -v rw >/dev/null && rw || mount -o remount,rw / ; }
ro(){ command -v ro >/dev/null && ro || mount -o remount,ro / ; }

# --- Connectivity check: give wpa_supplicant time, then look for a real
#     default route AND a reachable host. Only AP if BOTH fail. A live WiFi
#     link always has a default route, so this can't cut an existing connection.
sleep 15
online() {
    ip route 2>/dev/null | grep -q '^default' || return 1
    ping -c1 -W2 1.1.1.1 >/dev/null 2>&1 || ping -c1 -W2 8.8.8.8 >/dev/null 2>&1
}
if online; then
    echo "[$(date)] network is up (default route + reachable) — no portal needed"
    exit 0
fi
# double-check after a short grace period to avoid a transient false negative
sleep 8
if online; then echo "[$(date)] network came up on retry — exiting"; exit 0; fi

echo "[$(date)] no network — raising provisioning AP '$AP_SSID'"
command -v hostapd >/dev/null || pacman -Sy --noconfirm --needed hostapd 2>/dev/null
command -v dnsmasq  >/dev/null || pacman -Sy --noconfirm --needed dnsmasq 2>/dev/null

# free wlan0 from wpa_supplicant, bring up static AP IP
systemctl stop "wpa_supplicant@${AP_IFACE}" 2>/dev/null
systemctl stop wpa_supplicant 2>/dev/null
ip link set "$AP_IFACE" up
ip addr flush dev "$AP_IFACE" 2>/dev/null
ip addr add "${AP_IP}/24" dev "$AP_IFACE"

cat > /tmp/mb-hostapd.conf <<EOF
interface=$AP_IFACE
driver=nl80211
ssid=$AP_SSID
hw_mode=g
channel=6
auth_algs=1
wmm_enabled=0
EOF
cat > /tmp/mb-dnsmasq.conf <<EOF
interface=$AP_IFACE
bind-interfaces
dhcp-range=192.168.73.10,192.168.73.50,12h
address=/#/$AP_IP
no-resolv
no-hosts
EOF
pkill -f "hostapd /tmp/mb-hostapd" 2>/dev/null
pkill -f "dnsmasq.*mb-dnsmasq" 2>/dev/null
hostapd -B /tmp/mb-hostapd.conf -P /tmp/mb-hostapd.pid
sleep 1
dnsmasq -C /tmp/mb-dnsmasq.conf --pid-file=/tmp/mb-dnsmasq.pid
# captive redirect: all web traffic on the AP → the portal
iptables -t nat -A PREROUTING -i "$AP_IFACE" -p tcp --dport 80  -j DNAT --to-destination "${AP_IP}:${PORT}" 2>/dev/null
iptables -t nat -A PREROUTING -i "$AP_IFACE" -p tcp --dport 443 -j DNAT --to-destination "${AP_IP}:${PORT}" 2>/dev/null
echo "[$(date)] AP up — portal on ${AP_IP}:${PORT}"

# run the captive portal — blocks until the user submits credentials
rm -f "$WIFI_FILE" "$TS_KEY"
python3 "$PORTAL" "$AP_IP" "$PORT" "$WIFI_FILE" "$TS_KEY"
echo "[$(date)] portal exited ($?)"

# tear the AP back down no matter what
pkill -F /tmp/mb-hostapd.pid 2>/dev/null
pkill -F /tmp/mb-dnsmasq.pid 2>/dev/null
iptables -t nat -F PREROUTING 2>/dev/null
ip addr flush dev "$AP_IFACE" 2>/dev/null
sleep 1

# write the submitted WiFi into wpa_supplicant and reconnect
if [[ -f "$WIFI_FILE" ]]; then
    SSID=$(sed -n '1p' "$WIFI_FILE"); PASS=$(sed -n '2p' "$WIFI_FILE")
    echo "[$(date)] connecting to '$SSID'"
    rw
    if [[ -n "$PASS" ]]; then
        BLOCK=$(wpa_passphrase "$SSID" "$PASS" 2>/dev/null)
    else
        BLOCK=$'network={\n\tssid="'"$SSID"$'"\n\tkey_mgmt=NONE\n}'
    fi
    [[ -n "$BLOCK" ]] && printf '\n%s\n' "$BLOCK" >> "$WPA_CONF"
    ro
    rm -f "$WIFI_FILE"
    systemctl restart "wpa_supplicant@${AP_IFACE}" 2>/dev/null || systemctl restart wpa_supplicant 2>/dev/null
else
    # No creds submitted (portal timed out) — self-recover by rejoining whatever
    # saved networks exist, so a false trigger can never leave the radio stranded.
    echo "[$(date)] no creds submitted — rejoining saved networks"
    systemctl restart "wpa_supplicant@${AP_IFACE}" 2>/dev/null || systemctl restart wpa_supplicant 2>/dev/null
fi

# optional Tailscale auth key from the portal
if [[ -f "$TS_KEY" ]]; then
    K=$(cat "$TS_KEY"); rm -f "$TS_KEY"
    [[ -n "$K" ]] && tailscale up --authkey="$K" --accept-routes --reset 2>/dev/null
fi
echo "[$(date)] provisioning complete"
