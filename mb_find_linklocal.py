#!/usr/bin/env python3
r"""READ-ONLY: the direct Ethernet cable to the Pi has no DHCP server on it,
so both ends self-assign link-local (APIPA, 169.254.0.0/16) addresses. This
laptop's Ethernet NIC came up as 169.254.83.107. Broadcast-ping the
169.254.255.255 segment to make the Pi answer ARP, then sweep +/- around our
own address (self-assigned addresses often cluster), then try SSH.
"""
import os, sys, subprocess, re, traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(ROOT, "mb_find_linklocal_log.txt")
_logf = open(LOG, "w", encoding="utf-8", buffering=1)
def w(msg):
    print(msg)
    _logf.write(str(msg) + "\n")
    _logf.flush()

CREDS = [("root", "root"), ("raj", "lol")]

def get_linklocal_ip():
    out = subprocess.run(["ipconfig"], capture_output=True, text=True).stdout
    ips = re.findall(r"169\.254\.\d+\.\d+", out)
    return ips[0] if ips else None

def broadcast_ping():
    subprocess.run(["ping", "-n", "2", "-w", "500", "169.254.255.255"],
                    capture_output=True, text=True)

def sweep_local24(base):
    w(f"Sweeping {base}.0/24 (link-local segment)...")
    procs = []
    for i in range(1, 255):
        ip = f"{base}.{i}"
        p = subprocess.Popen(["ping", "-n", "1", "-w", "200", ip],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(p)
        if len(procs) >= 60:
            for pp in procs: pp.wait()
            procs = []
    for pp in procs: pp.wait()

def arp_all():
    out = subprocess.run(["arp", "-a"], capture_output=True, text=True).stdout
    return out

def main():
    try:
        import paramiko
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
        import paramiko

    my_ip = get_linklocal_ip()
    if not my_ip:
        w("No 169.254.x.x address found on this laptop right now — link-local IP may have changed.")
        w("Re-run mb_find_and_diag.py style discovery, or check ipconfig manually.")
        return 1
    w(f"Laptop link-local IP: {my_ip}")
    base = ".".join(my_ip.split(".")[:3])

    broadcast_ping()
    sweep_local24(base)

    out = arp_all()
    w("\n----- arp -a (link-local section) -----")
    # only show the section for this interface's neighborhood
    candidates = []
    for line in out.splitlines():
        m = re.search(r"(169\.254\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+dynamic", line)
        if m and m.group(1) != my_ip:
            candidates.append(m.group(1))
            w(line)
    if not candidates:
        w("(no other 169.254.x.x neighbors found in ARP table)")
        w("\nTrying full arp -a dump for visual inspection:")
        w(out)

    if not candidates:
        w("\nNo link-local neighbor found. The Pi may not have an Ethernet link at all")
        w("right now (cable/port issue), or it's on a different interface.")
        return 1

    w(f"\nCandidates: {candidates}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    hit = None
    for ip in candidates:
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
        w("\nFound link-local neighbor(s) but SSH failed with known creds.")
        return 1

    ip, user, pw = hit

    def run(cmd, label, t=30):
        w(f"\n===== {label} =====")
        w(f"$ {cmd}")
        try:
            ch = client.get_transport().open_session(); ch.settimeout(t); ch.exec_command(cmd)
            outb = b""
            while True:
                d = ch.recv(65535)
                if not d: break
                outb += d
            rc = ch.recv_exit_status()
            text = outb.decode(errors="replace").rstrip()
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
    print("See mb_find_linklocal_log.txt")
    sys.exit(rc)
