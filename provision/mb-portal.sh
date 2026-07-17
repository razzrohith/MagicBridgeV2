#!/usr/bin/env bash
# ============================================================
#  MagicBridgeV2 WiFi provisioning AP (captive portal)
#
#  Boot service (mb-portal.service). If the device has no working network,
#  it raises an open "MagicBridge-Setup" hotspot + captive portal and KEEPS
#  IT UP until someone submits WiFi credentials that actually connect. Wrong
#  credentials just reopen the hotspot to try again. Re-checks every boot.
#
#  Adapted for PiKVM OS (Arch + wpa_supplicant, read-only rootfs).
#  Recovery: serial/SSH always works; this never touches a live link.
#  SSID: MagicBridge-Setup (open)   Portal: http://192.168.73.1/
# ============================================================
set +e   # never abort mid-teardown — stranding the radio is worse than any error

LOG="/run/mb-portal.log"   # /run is tmpfs (always writable, even on read-only rootfs)
AP_SSID="MagicBridge-Setup"
AP_IP="192.168.73.1"
AP_IFACE="wlan0"
PORT=8080
PORTAL="/opt/magicbridge/provision/portal.py"
WIFI_FILE="/tmp/mb-provision-wifi"
TS_KEY="/tmp/mb-provision-tskey"
WPA_CONF="/etc/wpa_supplicant/wpa_supplicant-${AP_IFACE}.conf"
exec >> "$LOG" 2>&1
echo "[$(date)] mb-portal starting"

rw(){ command -v rw >/dev/null && rw || mount -o remount,rw / ; }
ro(){ command -v ro >/dev/null && ro || mount -o remount,ro / ; }

online(){ ip route 2>/dev/null | grep -q '^default' || return 1
          ping -c1 -W2 1.1.1.1 >/dev/null 2>&1 || ping -c1 -W2 8.8.8.8 >/dev/null 2>&1; }
# "really joined a WiFi": associated AND has an IPv4 on wlan0
wlan_connected(){ iw dev "$AP_IFACE" link 2>/dev/null | grep -qi 'Connected to' \
                  && ip -4 addr show "$AP_IFACE" 2>/dev/null | grep -q 'inet '; }

setup_ap(){
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
except-interface=lo
bind-dynamic
dhcp-range=192.168.73.10,192.168.73.50,12h
dhcp-leasefile=/run/mb-dnsmasq.leases
dhcp-authoritative
address=/#/$AP_IP
no-resolv
no-hosts
EOF
    pkill -f "hostapd /tmp/mb-hostapd" 2>/dev/null
    pkill -f "dnsmasq.*mb-dnsmasq" 2>/dev/null
    sleep 1
    hostapd -B /tmp/mb-hostapd.conf -P /tmp/mb-hostapd.pid
    sleep 1
    dnsmasq -C /tmp/mb-dnsmasq.conf --pid-file=/tmp/mb-dnsmasq.pid
    iptables -t nat -A PREROUTING -i "$AP_IFACE" -p tcp --dport 80  -j DNAT --to-destination "${AP_IP}:${PORT}" 2>/dev/null
    iptables -t nat -A PREROUTING -i "$AP_IFACE" -p tcp --dport 443 -j DNAT --to-destination "${AP_IP}:${PORT}" 2>/dev/null
    echo "[$(date)] AP '$AP_SSID' up — portal on ${AP_IP}:${PORT}"
}

teardown_ap(){
    pkill -F /tmp/mb-hostapd.pid 2>/dev/null
    pkill -F /tmp/mb-dnsmasq.pid 2>/dev/null
    iptables -t nat -F PREROUTING 2>/dev/null
    ip addr flush dev "$AP_IFACE" 2>/dev/null
    sleep 1
}

apply_wifi(){
    local SSID PASS BLOCK
    SSID=$(sed -n '1p' "$WIFI_FILE"); PASS=$(sed -n '2p' "$WIFI_FILE")
    echo "[$(date)] applying WiFi '$SSID'"
    rw
    if [ -n "$PASS" ]; then
        BLOCK=$(wpa_passphrase "$SSID" "$PASS" 2>/dev/null)
    else
        BLOCK=$'network={\n\tssid="'"$SSID"$'"\n\tkey_mgmt=NONE\n}'
    fi
    [ -n "$BLOCK" ] && printf '\n%s\n' "$BLOCK" >> "$WPA_CONF"
    ro
    rm -f "$WIFI_FILE"
    ip addr flush dev "$AP_IFACE" 2>/dev/null
    systemctl restart "wpa_supplicant@${AP_IFACE}" 2>/dev/null || systemctl restart wpa_supplicant 2>/dev/null
    systemctl restart systemd-networkd 2>/dev/null
}

remove_last_wifi(){
    # Drop the network block we just appended so a bad password doesn't pile up.
    rw
    if grep -q '^network={' "$WPA_CONF" 2>/dev/null; then
        # delete from the LAST 'network={' to its closing '}'
        awk 'BEGIN{RS="";FS="\n"} {print}' >/dev/null 2>&1
        LAST=$(grep -n '^network={' "$WPA_CONF" | tail -1 | cut -d: -f1)
        [ -n "$LAST" ] && sed -i "${LAST},/^}/d" "$WPA_CONF"
    fi
    ro
}

# ---------------- main ----------------
sleep 15
if online; then echo "[$(date)] already online — nothing to do"; exit 0; fi

# Keep provisioning until we actually join a real WiFi network.
while true; do
    setup_ap
    echo "[$(date)] waiting for credentials (no timeout) ..."
    rm -f "$WIFI_FILE" "$TS_KEY"
    python3 "$PORTAL" "$AP_IP" "$PORT" "$WIFI_FILE" "$TS_KEY"   # blocks until submit
    teardown_ap

    if [ ! -f "$WIFI_FILE" ]; then
        echo "[$(date)] portal exited with no credentials — reopening hotspot"
        continue
    fi

    apply_wifi
    if [ -f "$TS_KEY" ]; then
        K=$(cat "$TS_KEY"); rm -f "$TS_KEY"
        [ -n "$K" ] && tailscale up --authkey="$K" --accept-routes --reset 2>/dev/null
    fi

    echo "[$(date)] verifying connection (up to ~50s) ..."
    for i in $(seq 1 16); do sleep 3; wlan_connected && break; done
    if wlan_connected; then
        echo "[$(date)] CONNECTED to WiFi — provisioning complete"
        touch /run/mb-provisioned
        exit 0
    fi

    echo "[$(date)] could not connect (bad password / out of range) — reopening hotspot"
    remove_last_wifi
done
