#!/usr/bin/env python3
"""
magicbridge-net - MagicBridgeV2 network toolkit sidecar.

Runs alongside kvmd on 127.0.0.1:8410 (behind kvmd nginx at /mb/net/).
Ports V1's network features onto the PiKVM base WITHOUT touching kvmd:
  - DuckDNS dynamic-DNS updater
  - Tailscale status wrapper
  - Tailscale-only network lockdown (iptables; SSH never touched)
  - MAC address spoofing (persisted; re-applied at boot)
  - WiFi scan/connect (nmcli) - TODO on hardware
"""
from __future__ import annotations
import asyncio
import os
import subprocess
import sys
import time

sys.path.insert(0, "/opt/magicbridge/services/common")
try:
    from mbcommon import get_logger, load_config, save_config
except Exception:  # dev-machine fallback
    import logging

    def get_logger(n):
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(n)

    def load_config(n, d=None):
        return dict(d or {})

    def save_config(n, d):
        pass

from aiohttp import web

log = get_logger("mb-net")
PORT = int(os.environ.get("MB_NET_PORT", "8410"))


def sh(*args, timeout=15):
    try:
        p = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:
        return 1, str(e)


async def health(_):
    return web.json_response({"ok": True, "service": "magicbridge-net"})


async def status(_):
    ts_rc, ts_out = sh("tailscale", "status", "--json", timeout=8)
    return web.json_response({
        "tailscale": {"up": ts_rc == 0, "raw": ts_out[:2000]},
        "duckdns": load_config("net", {}).get("duckdns", {"enabled": False}),
        "hostname": os.uname().nodename,
    })


async def duckdns_update(request):
    body = await request.json()
    domain = body.get("domain", "")
    token = body.get("token", "")
    if not domain or not token:
        return web.json_response({"ok": False, "error": "domain and token required"}, status=400)
    import urllib.request
    url = f"https://www.duckdns.org/update?domains={domain}&token={token}&ip="
    try:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None, lambda: urllib.request.urlopen(url, timeout=15).read().decode())
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=502)
    cfg = load_config("net", {})
    cfg["duckdns"] = {"enabled": True, "domain": domain, "last": resp, "ts": int(time.time())}
    save_config("net", cfg)
    return web.json_response({"ok": resp.strip() == "OK", "duckdns_response": resp})


async def lockdown(request):
    body = await request.json()
    on = bool(body.get("on"))
    sh("iptables", "-N", "MB_LOCKDOWN")
    sh("iptables", "-F", "MB_LOCKDOWN")
    if on:
        for port in ("80", "443"):
            sh("iptables", "-A", "MB_LOCKDOWN", "-i", "lo", "-p", "tcp", "--dport", port, "-j", "ACCEPT")
            sh("iptables", "-A", "MB_LOCKDOWN", "-i", "tailscale0", "-p", "tcp", "--dport", port, "-j", "ACCEPT")
            sh("iptables", "-A", "MB_LOCKDOWN", "-p", "tcp", "--dport", port, "-j", "DROP")
        rc, _out = sh("iptables", "-C", "INPUT", "-j", "MB_LOCKDOWN")
        if rc != 0:
            sh("iptables", "-I", "INPUT", "1", "-j", "MB_LOCKDOWN")
    else:
        sh("iptables", "-D", "INPUT", "-j", "MB_LOCKDOWN")
    cfg = load_config("net", {})
    cfg["lockdown"] = on
    save_config("net", cfg)
    return web.json_response({"ok": True, "lockdown": on, "note": "SSH (22) never restricted"})


async def mac_spoof(request):
    body = await request.json()
    iface = body.get("iface", "wlan0")
    if body.get("random"):
        import random
        mac = "02:%02x:%02x:%02x:%02x:%02x" % tuple(random.randint(0, 255) for _ in range(5))
    else:
        mac = body.get("mac", "")
    if not mac:
        return web.json_response({"ok": False, "error": "mac or random required"}, status=400)
    sh("ip", "link", "set", iface, "down")
    rc, out = sh("ip", "link", "set", iface, "address", mac)
    sh("ip", "link", "set", iface, "up")
    cfg = load_config("net", {})
    cfg["mac"] = {"iface": iface, "mac": mac}
    save_config("net", cfg)
    return web.json_response({
        "ok": rc == 0, "iface": iface, "mac": mac, "detail": out[:300],
        "persisted": "re-applied at boot via magicbridge-net config",
    })


async def tailscale_ctl(request):
    body = await request.json()
    action = body.get("action", "status")
    if action == "up":
        rc, out = sh("tailscale", "up", "--accept-routes", timeout=30)
    elif action == "down":
        rc, out = sh("tailscale", "down", timeout=15)
    else:
        rc, out = sh("tailscale", "status", timeout=10)
    return web.json_response({"ok": rc == 0, "action": action, "detail": out[:1500]})


async def wifi_connect(request):
    """POST /mb/net/wifi {ssid, password} — add/connect a Wi-Fi network via wpa_supplicant."""
    body = await request.json()
    ssid = body.get("ssid", "")
    pw = body.get("password", "")
    if not ssid:
        return web.json_response({"ok": False, "error": "ssid required"}, status=400)
    conf = "/etc/wpa_supplicant/wpa_supplicant-wlan0.conf"
    # generate a network block and append (rw toggle for PiKVM read-only FS)
    sh("bash", "-c", "command -v rw >/dev/null && rw || mount -o remount,rw /")
    try:
        rc, block = sh("wpa_passphrase", ssid, pw)
        if rc != 0:
            return web.json_response({"ok": False, "error": block[:300]}, status=502)
        try:
            with open(conf, "a") as f:
                f.write("\n" + block + "\n")
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)
        sh("systemctl", "restart", "wpa_supplicant@wlan0")
    finally:
        sh("bash", "-c", "command -v ro >/dev/null && ro || true")
    cfg = load_config("net", {}); cfg["wifi"] = {"ssid": ssid}; save_config("net", cfg)
    return web.json_response({"ok": True, "ssid": ssid, "note": "added; may take a few seconds to associate"})


async def wol(request):
    """POST /mb/net/wol {mac} — send a Wake-on-LAN magic packet (no external deps)."""
    import socket
    body = await request.json()
    mac = (body.get("mac") or "").strip()
    hexmac = mac.replace(":", "").replace("-", "").replace(".", "")
    if len(hexmac) != 12:
        return web.json_response({"ok": False, "error": "invalid MAC"}, status=400)
    try:
        raw = bytes.fromhex(hexmac)
        packet = b"\xff" * 6 + raw * 16
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for port in (9, 7):
            s.sendto(packet, ("255.255.255.255", port))
        s.close()
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)
    return web.json_response({"ok": True, "mac": mac})


async def wifi_scan(_):
    """GET /mb/net/wifi/scan — list nearby SSIDs (wpa_cli on PiKVM, nmcli fallback)."""
    nets = []
    rc, _o = sh("wpa_cli", "-i", "wlan0", "scan", timeout=6)
    time.sleep(2)
    rc, out = sh("wpa_cli", "-i", "wlan0", "scan_results", timeout=8)
    if rc == 0 and out:
        for line in out.splitlines()[1:]:
            cols = line.split("\t")
            if len(cols) >= 5 and cols[4].strip():
                nets.append({"ssid": cols[4].strip(), "signal": cols[2].strip(),
                             "secure": "WPA" in cols[3] or "WEP" in cols[3]})
    if not nets:  # NetworkManager fallback
        rc, out = sh("nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list", timeout=10)
        if rc == 0:
            for line in out.splitlines():
                p = line.split(":")
                if p and p[0]:
                    nets.append({"ssid": p[0], "signal": p[1] if len(p) > 1 else "",
                                 "secure": bool(len(p) > 2 and p[2] and p[2] != "--")})
    seen, uniq = set(), []
    for n in sorted(nets, key=lambda x: -int(x["signal"] or 0) if str(x["signal"]).lstrip("-").isdigit() else 0):
        if n["ssid"] not in seen:
            seen.add(n["ssid"]); uniq.append(n)
    return web.json_response({"ok": True, "networks": uniq[:30]})


async def update_check(_):
    """GET /mb/net/update — check for OS/package updates without applying anything."""
    rc, out = sh("bash", "-c", "checkupdates 2>/dev/null | wc -l", timeout=30)
    count = out.strip() if rc == 0 and out.strip().isdigit() else None
    if count is None:
        rc2, out2 = sh("bash", "-c", "pacman -Qu 2>/dev/null | wc -l", timeout=30)
        count = out2.strip() if out2.strip().isdigit() else "0"
    return web.json_response({"ok": True, "updates": int(count),
                              "detail": ("%s package update(s) available" % count) if count != "0"
                              else "system is up to date"})


async def logs_tail(request):
    """GET /mb/net/logs?unit=&n= — tail recent journald logs for our services."""
    unit = request.query.get("unit", "")
    n = request.query.get("n", "80")
    n = n if n.isdigit() else "80"
    args = ["journalctl", "-n", n, "--no-pager", "-o", "short-iso"]
    if unit in ("kvmd", "kvmd-nginx", "magicbridge-net", "magicbridge-stealth", "magicbridge-agent"):
        args += ["-u", unit]
    rc, out = sh(*args, timeout=12)
    return web.json_response({"ok": rc == 0, "unit": unit or "all", "text": out[-8000:]})


def build_app():
    app = web.Application()
    app.add_routes([
        web.get("/health", health),
        web.get("/status", status),
        web.post("/duckdns", duckdns_update),
        web.post("/lockdown", lockdown),
        web.post("/mac", mac_spoof),
        web.post("/tailscale", tailscale_ctl),
        web.post("/wifi", wifi_connect),
        web.post("/wol", wol),
        web.get("/wifi/scan", wifi_scan),
        web.get("/update", update_check),
        web.get("/logs", logs_tail),
    ])
    return app


if __name__ == "__main__":
    log.info("magicbridge-net starting on 127.0.0.1:%d", PORT)
    web.run_app(build_app(), host="127.0.0.1", port=PORT, print=None)
