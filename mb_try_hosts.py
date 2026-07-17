#!/usr/bin/env python3
r"""READ-ONLY: try SSH (both known MagicBridge cred sets) against every live
host found on this laptop's real subnet (192.168.1.0/24), since MAC-vendor
matching found nothing (MAC spoofing may be active). On success, run the
wifi/AP diagnostic.
"""
import os, sys, subprocess, traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(ROOT, "mb_try_hosts_log.txt")
_logf = open(LOG, "w", encoding="utf-8", buffering=1)
def w(msg):
    print(msg)
    _logf.write(str(msg) + "\n")
    _logf.flush()

HOSTS = ["192.168.1.2", "192.168.1.32", "192.168.1.1"]
CREDS = [("root", "root"), ("raj", "lol")]

def main():
    try:
        import paramiko
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
        import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    hit = None
    for ip in HOSTS:
        for user, pw in CREDS:
            try:
                client.connect(ip, username=user, password=pw, timeout=6,
                               allow_agent=False, look_for_keys=False)
                w(f"[ok] {ip} as {user}/{pw}")
                hit = (ip, user, pw)
                break
            except Exception as e:
                w(f"[skip] {ip} as {user}/{pw}: {e}")
        if hit:
            break

    if not hit:
        w("\nNo SSH access on any live host with known creds.")
        w("This confirms the Pi is either unreachable on this subnet, or")
        w("its Ethernet hasn't picked up an IP yet. Check the OLED screen")
        w("on the V4 Mini itself (if lit) for its current IP address.")
        return 1

    ip, user, pw = hit

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

    run("hostnamectl 2>/dev/null | head -5; echo ---; cat /etc/hostname 2>/dev/null", "identity")
    run("ip -br addr; echo ---ROUTE---; ip route", "interfaces + routes")
    run("rfkill list 2>/dev/null || echo 'rfkill not available'", "rfkill (is WiFi soft/hard blocked?)")
    run("iw dev 2>/dev/null || echo 'iw not available / no wireless dev'", "iw dev (does wlan0 exist?)")
    run("ls -l /sys/class/net/ | grep -i wlan || echo 'NO wlan interface in /sys/class/net'", "wlan in /sys/class/net")
    run("iw list 2>/dev/null | sed -n '/Supported interface modes/,/Supported commands/p' "
        "| grep -Ei 'AP|managed|monitor' || echo 'could not read supported modes'",
        "AP-mode capability (must list '* AP')")
    run("iw dev wlan0 scan 2>/dev/null | grep -E 'SSID|signal' | head -40 "
        "|| echo 'scan failed (radio down, no antenna, or blocked)'",
        "WiFi scan at this location")
    run("systemctl is-enabled mb-portal.service 2>&1; echo ---; "
        "systemctl status mb-portal.service --no-pager -l 2>&1 | head -25", "mb-portal.service state")
    run("tail -n 80 /var/lib/magicbridge/portal.log 2>/dev/null || echo 'no portal.log yet'",
        "portal.log (the service's own record of what happened)")
    run("for b in hostapd dnsmasq wpa_passphrase python3; do printf '%-14s ' \"$b:\"; "
        "command -v $b || echo MISSING; done", "AP dependencies present?")
    run("grep -E 'ssid=|network=' /etc/wpa_supplicant/wpa_supplicant-wlan0.conf 2>/dev/null "
        "|| grep -rEl 'ssid=' /etc/wpa_supplicant/ 2>/dev/null || echo 'no wpa_supplicant wlan0 conf found'",
        "saved WiFi networks")
    run("systemctl is-active kvmd kvmd-nginx magicbridge-net 2>&1", "core services")

    client.close()
    w(f"\n=== diagnostic done. Reachable at {ip} as {user} ===")
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
    print("See mb_try_hosts_log.txt")
    sys.exit(rc)
