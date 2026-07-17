#!/usr/bin/env python3
r"""
READ-ONLY: find the V4 Mini on this new network (mDNS failed - no
magicbridge.local), then run the same wifi/AP diagnostic against it.

Strategy:
  1. Find this laptop's IPv4 + /24 subnet.
  2. Ping-sweep the subnet (fast, best-effort) to populate the ARP cache.
  3. Read `arp -a` and keep only MACs whose vendor OUI belongs to
     Raspberry Pi Trading Ltd (the V4 Mini's CM4 NIC).
  4. Try SSH (root/root) against each candidate, in order.
  5. On success, run the same checks as mb_diag_wifi_ap.py.

Changes NOTHING on the Pi.
"""
import os, sys, socket, subprocess, re, traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(ROOT, "mb_find_and_diag_log.txt")
_logf = open(LOG, "w", encoding="utf-8", buffering=1)
def w(msg):
    print(msg)
    _logf.write(str(msg) + "\n")
    _logf.flush()

# Raspberry Pi Foundation / Trading Ltd OUI prefixes (first 3 octets, upper, colon-joined)
PI_OUIS = {
    "B8:27:EB", "DC:A6:32", "E4:5F:01", "28:CD:C1", "D8:3A:DD",
    "2C:CF:67", "3A:35:41",
}

PI_USER, PI_PASS = "root", "root"

def get_local_subnet():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = socket.gethostbyname(socket.gethostname())
    finally:
        s.close()
    parts = ip.split(".")
    base = ".".join(parts[:3])
    return ip, base

def ping_sweep(base):
    w(f"Ping-sweeping {base}.1-254 (best effort, ~30s)...")
    procs = []
    for i in range(1, 255):
        ip = f"{base}.{i}"
        p = subprocess.Popen(
            ["ping", "-n", "1", "-w", "300", ip],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        procs.append(p)
        if len(procs) >= 40:
            for pp in procs: pp.wait()
            procs = []
    for pp in procs: pp.wait()
    w("Ping sweep done.")

def arp_candidates():
    out = subprocess.run(["arp", "-a"], capture_output=True, text=True).stdout
    w("\n----- arp -a raw -----")
    w(out)
    candidates = []
    for line in out.splitlines():
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})", line)
        if not m:
            continue
        ip, mac = m.group(1), m.group(2).replace("-", ":").upper()
        oui = ":".join(mac.split(":")[:3])
        if oui in PI_OUIS:
            candidates.append((ip, mac))
    return candidates

def main():
    try:
        import paramiko
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
        import paramiko

    my_ip, base = get_local_subnet()
    w(f"Laptop IP: {my_ip}  subnet: {base}.0/24")

    ping_sweep(base)
    candidates = arp_candidates()

    if not candidates:
        w("\nNo Raspberry-Pi-vendor MAC found in ARP table after sweep.")
        w("=> The Pi may be on a different VLAN/subnet than this laptop's WiFi/Ethernet,")
        w("   or its NIC MAC isn't in the known OUI list. Open the KVM page manually")
        w("   (if you know its IP) or check your router's connected-devices list.")
        return 1

    w(f"\nCandidate Pi-vendor hosts: {candidates}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connected_ip = None
    for ip, mac in candidates:
        try:
            client.connect(ip, username=PI_USER, password=PI_PASS, timeout=8,
                           allow_agent=False, look_for_keys=False)
            connected_ip = ip
            w(f"[ok] SSH connected to {ip} ({mac})")
            break
        except Exception as e:
            w(f"[skip] {ip} ({mac}): SSH failed ({e})")

    if not connected_ip:
        w("\nFound Pi-vendor MAC(s) but SSH (root/root) failed on all of them.")
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

    run("hostnamectl 2>/dev/null | head -5; echo ---; cat /etc/hostname", "identity")
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
    run("tail -n 60 /var/lib/magicbridge/portal.log 2>/dev/null || echo 'no portal.log yet'",
        "portal.log (the service's own record of what happened)")
    run("for b in hostapd dnsmasq wpa_passphrase python3; do printf '%-14s ' \"$b:\"; "
        "command -v $b || echo MISSING; done", "AP dependencies present?")
    run("grep -E 'ssid=|network=' /etc/wpa_supplicant/wpa_supplicant-wlan0.conf 2>/dev/null "
        "|| grep -rEl 'ssid=' /etc/wpa_supplicant/ 2>/dev/null || echo 'no wpa_supplicant wlan0 conf found'",
        "saved WiFi networks")

    client.close()
    w(f"\n=== diagnostic done. Pi reachable at {connected_ip} ===")
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
    print("See mb_find_and_diag_log.txt")
    sys.exit(rc)
