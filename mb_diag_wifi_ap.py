#!/usr/bin/env python3
r"""
READ-ONLY diagnostic: why did the "MagicBridge-Setup" hotspot NOT come up
when the V4 Mini was powered on at a new location with no known WiFi?

Changes NOTHING on the Pi. It only reads state and answers:
  - Does wlan0 exist at all? (V4 Mini needs the CM4 WiFi antenna kit)
  - Is WiFi blocked by rfkill?
  - Can wlan0 actually run as an Access Point (AP mode capable)?
  - Can it see this location's WiFi networks (scan)?
  - What does the portal's own log say happened at last boot?
  - Is mb-portal.service enabled / did it run?

The old IP (172.16.20.209) is stale now that you're on new WiFi, so this
connects BY HOSTNAME over the Ethernet cable you plugged in. If none of the
hostnames resolve, open the KVM page in a browser, read the IP it's on, and
put it in PI_IP_OVERRIDE below.

Run:  Alt+D in File Explorer ->
  cmd /c python C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\mb_diag_wifi_ap.py
Then check  mb_diag_wifi_ap_log.txt  in the same folder and paste it back.
"""
import os, sys, socket, traceback

# If hostname resolution fails, put the Ethernet IP the KVM page shows here:
PI_IP_OVERRIDE = ""          # e.g. "192.168.1.57"
CANDIDATE_HOSTS = ["magicbridge.local", "pikvm.local", "kvmd.local"]
PI_USER, PI_PASS = "root", "root"

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(ROOT, "mb_diag_wifi_ap_log.txt")
_logf = open(LOG, "w", encoding="utf-8", buffering=1)
def w(msg):
    print(msg)
    _logf.write(str(msg) + "\n")
    _logf.flush()

def main():
    try:
        import paramiko
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
        import paramiko

    # Build the host list: override first, then mDNS hostnames.
    hosts = ([PI_IP_OVERRIDE] if PI_IP_OVERRIDE.strip() else []) + CANDIDATE_HOSTS
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connected_host = None
    for h in hosts:
        try:
            ip = socket.gethostbyname(h)
        except Exception as e:
            w(f"[skip] {h}: cannot resolve ({e})")
            continue
        try:
            client.connect(h, username=PI_USER, password=PI_PASS, timeout=12,
                           allow_agent=False, look_for_keys=False)
            connected_host = h
            w(f"[ok] connected to {h} ({ip}) as {PI_USER}")
            break
        except Exception as e:
            w(f"[skip] {h} ({ip}): SSH failed ({e})")

    if not connected_host:
        w("\nCOULD NOT CONNECT to any candidate host.")
        w("=> Open the KVM web page over the Ethernet cable, read the IP it is on,")
        w("   put it in PI_IP_OVERRIDE at the top of this script, and run again.")
        return 1

    def run(cmd, label, t=30):
        w(f"\n===== {label} =====")
        w(f"$ {cmd}")
        try:
            ch = client.get_transport().open_session(); ch.settimeout(t); ch.exec_command(cmd)
            out = b""
            while True:
                d = ch.recv(65535)
                if not d: break
                out += d
            rc = ch.recv_exit_status()
            text = out.decode(errors="replace").rstrip()
            if text: w(text)
            w(f"[exit {rc}]")
        except Exception as e:
            w(f"[error running: {e}]")

    # --- Identity / network state
    run("hostnamectl 2>/dev/null | head -5; echo ---; cat /etc/hostname", "identity")
    run("ip -br addr; echo ---ROUTE---; ip route", "interfaces + routes")

    # --- Is there a WiFi radio at all, and is it blocked?
    run("rfkill list 2>/dev/null || echo 'rfkill not available'", "rfkill (is WiFi soft/hard blocked?)")
    run("iw dev 2>/dev/null || echo 'iw not available / no wireless dev'", "iw dev (does wlan0 exist?)")
    run("ls -l /sys/class/net/ | grep -i wlan || echo 'NO wlan interface in /sys/class/net'", "wlan in /sys/class/net")

    # --- Can wlan0 actually be an Access Point? (this is what hostapd needs)
    run("iw list 2>/dev/null | sed -n '/Supported interface modes/,/Supported commands/p' "
        "| grep -Ei 'AP|managed|monitor' || echo 'could not read supported modes'",
        "AP-mode capability (must list '* AP')")

    # --- Can it see this location's WiFi? (proves antenna + radio work)
    run("iw dev wlan0 scan 2>/dev/null | grep -E 'SSID|signal' | head -40 "
        "|| echo 'scan failed (radio down, no antenna, or blocked)'",
        "WiFi scan at this location")

    # --- What did the portal service actually do at last boot?
    run("systemctl is-enabled mb-portal.service 2>&1; echo ---; "
        "systemctl status mb-portal.service --no-pager -l 2>&1 | head -25", "mb-portal.service state")
    run("tail -n 60 /var/lib/magicbridge/portal.log 2>/dev/null || echo 'no portal.log yet'",
        "portal.log (the service's own record of what happened)")

    # --- Are the AP tools present?
    run("for b in hostapd dnsmasq wpa_passphrase python3; do printf '%-14s ' \"$b:\"; "
        "command -v $b || echo MISSING; done", "AP dependencies present?")

    # --- Saved WiFi networks
    run("grep -E 'ssid=|network=' /etc/wpa_supplicant/wpa_supplicant-wlan0.conf 2>/dev/null "
        "|| grep -rEl 'ssid=' /etc/wpa_supplicant/ 2>/dev/null || echo 'no wpa_supplicant wlan0 conf found'",
        "saved WiFi networks")

    client.close()
    w("\n=== diagnostic done — paste this whole log back ===")
    return 0

if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        w("\nUNCAUGHT EXCEPTION:")
        w(traceback.format_exc())
        rc = 1
    finally:
        _logf.close()
    print("See mb_diag_wifi_ap_log.txt")
    sys.exit(rc)
